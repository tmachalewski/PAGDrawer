"""GML-0 — Corpus exporter for the Graph-ML EPSS prediction task.

Turns a list of enriched CVE dicts (the output of the Trivy/deployment
loaders) into the ML corpus described in
`Docs/Plans/GraphML_EPSS_Prediction.md` §3:

  * nodes   — unique CVEs (deduplicated by CVE id, per D3)
  * features— raw, encoding-agnostic (CVSS vector, CWE ids, technical
              impacts, description, age); tensor encoding happens later in
              the training script, so the export stays deterministic
  * edges   — directed ``enables`` relation, ``a -> b`` iff outcomes(a)
              satisfy prereqs(b), using the single-source-of-truth predicate
              ``consensual_matrix.prereqs_satisfied`` (per D5 / §9)
  * label   — EPSS score kept on the node but flagged as label, NEVER a
              feature (per D3)
  * diagnostics — degree histograms, quotient-class census, isolated-node
              share (per D13 / GML-0 acceptance)

The core (`build_corpus`) is pure: it takes plain dicts and returns plain
data, so it is unit-testable on a synthetic mini-corpus without Mongo, a
network, or a Cytoscape/graph instance.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from src.core.consensual_matrix import (
    extract_prerequisites,
    get_post_exploitation_vcs,
    prereqs_satisfied,
)

# Bump only on breaking changes to the exported JSON shape (renamed/removed
# keys). Adding fields is non-breaking and stays at this version.
SCHEMA_VERSION = 1


# =============================================================================
# VC helpers — outcomes / prereqs / quotient keys
# =============================================================================

def outcomes_of(technical_impacts: Sequence[str]) -> Set[Tuple[str, str]]:
    """Union of Vector-Changer outcomes over a CVE's technical impacts.

    Mirrors how the graph builder accumulates a CVE's post-exploitation VCs:
    each technical impact maps through the consensual matrix, and a CVE that
    lists several impacts grants the union of their outcomes.
    """
    out: Set[Tuple[str, str]] = set()
    for impact in technical_impacts or []:
        out.update(get_post_exploitation_vcs(impact))
    return out


def prereqs_of(cvss_vector: str) -> List[Tuple[str, str]]:
    """Chain prerequisites (AV/PR) extracted from a CVE's CVSS vector."""
    return extract_prerequisites(cvss_vector)


def _canon_pairs(pairs: Set[Tuple[str, str]] | List[Tuple[str, str]]) -> str:
    """Deterministic string key for a set/list of (type, value) VC pairs."""
    if not pairs:
        return "none"
    return ",".join(f"{t}:{v}" for t, v in sorted(set(pairs)))


def prereq_key(cvss_vector: str) -> str:
    """Quotient key for a CVE's prerequisites (the 'in' side of enables)."""
    return _canon_pairs(prereqs_of(cvss_vector))


def outcome_key(technical_impacts: Sequence[str]) -> str:
    """Quotient key for a CVE's outcomes (the 'out' side of enables)."""
    return _canon_pairs(outcomes_of(technical_impacts))


def enables(a_outcomes: Set[Tuple[str, str]], b_prereqs: List[Tuple[str, str]]) -> bool:
    """``a enables b`` — do a's outcomes satisfy b's prerequisites?

    Thin wrapper over the single source of truth so the exporter never
    re-derives the predicate (§9).
    """
    return prereqs_satisfied(b_prereqs, a_outcomes)


# =============================================================================
# Corpus data classes
# =============================================================================

@dataclass
class CorpusNode:
    """One deduplicated CVE in the ML corpus.

    Feature fields are raw (encoding happens in the training script). The
    label (`epss_score`) rides along but is flagged, never fed as a feature.
    """
    cve_id: str
    # --- features (raw) ---
    cvss_vector: str
    cwe_ids: List[str]
    technical_impacts: List[str]
    description: str = ""
    age_days: Optional[int] = None          # days since publication
    modified_age_days: Optional[int] = None  # days since last NVD modification
    # --- derived quotient keys ---
    prereq_key: str = ""
    outcome_key: str = ""
    # --- label (never a feature) ---
    epss_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CorpusEdge:
    """A directed ``enables`` edge: source's outcomes satisfy target's prereqs."""
    source: str  # cve_id of the enabler
    target: str  # cve_id of the enabled

    def to_dict(self) -> Dict[str, str]:
        return {"source": self.source, "target": self.target}


@dataclass
class CorpusDiagnostics:
    """GML-0 diagnostics — characterize the graph before any GNN is written."""
    node_count: int
    edge_count: int
    self_loop_count: int
    isolated_node_count: int
    isolated_node_share: float
    # quotient census: how many distinct (prereq_key, outcome_key) classes,
    # and the membership sizes of the largest few
    quotient_class_count: int
    largest_quotient_classes: List[Tuple[str, int]]
    # degree histograms {degree: how many nodes have it}
    in_degree_histogram: Dict[int, int]
    out_degree_histogram: Dict[int, int]
    # CVEs with no prereqs and/or no outcomes (structural sources/sinks)
    no_prereq_count: int
    no_outcome_count: int

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # tuples -> lists for clean JSON
        d["largest_quotient_classes"] = [list(t) for t in self.largest_quotient_classes]
        return d


@dataclass
class Corpus:
    schema_version: int
    nodes: List[CorpusNode]
    edges: List[CorpusEdge]
    diagnostics: CorpusDiagnostics
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "meta": self.meta,
            "diagnostics": self.diagnostics.to_dict(),
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }


# =============================================================================
# Build
# =============================================================================

def _dedupe_by_cve(cve_dicts: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One entry per CVE id (per D3). First occurrence wins; later copies of
    the same CVE are identical in the label-relevant fields (EPSS/CVSS/CWE are
    per-CVE globals), so any deterministic choice is fine. We keep first-seen
    order for stable output.
    """
    seen: Set[str] = set()
    out: List[Dict[str, Any]] = []
    for c in cve_dicts:
        cid = (c.get("id") or "").split("@")[0].upper()
        if not cid or cid in seen:
            continue
        seen.add(cid)
        out.append(c)
    return out


def _histogram(values: Sequence[int]) -> Dict[int, int]:
    return dict(sorted(Counter(values).items()))


def build_corpus(
    cve_dicts: Sequence[Dict[str, Any]],
    *,
    include_self_loops: bool = False,
    meta: Optional[Dict[str, Any]] = None,
) -> Corpus:
    """Build the ML corpus from enriched CVE dicts.

    Args:
        cve_dicts: enriched CVE records (loader output). Required keys per
            record: ``id``, ``cvss_vector``; optional: ``cwe_ids``,
            ``technical_impacts``, ``description``, ``epss_score``,
            ``age_days``, ``modified_age_days``.
        include_self_loops: whether a CVE that enables itself (its own
            outcomes satisfy its own prereqs) gets a self-edge. Default False
            — self-loops carry no chain information and complicate the GNN.
        meta: free-form provenance (label snapshot date, git SHA, corpus
            source) copied into the export verbatim.

    Returns:
        A ``Corpus`` with deduped nodes, ``enables`` edges, and diagnostics.
    """
    deduped = _dedupe_by_cve(cve_dicts)

    nodes: List[CorpusNode] = []
    # precompute per-node outcomes/prereqs once
    node_outcomes: Dict[str, Set[Tuple[str, str]]] = {}
    node_prereqs: Dict[str, List[Tuple[str, str]]] = {}

    for c in deduped:
        cid = c["id"].split("@")[0].upper()
        cvss = c.get("cvss_vector", "") or ""
        impacts = list(c.get("technical_impacts", []) or [])
        outs = outcomes_of(impacts)
        pres = prereqs_of(cvss)
        node_outcomes[cid] = outs
        node_prereqs[cid] = pres

        nodes.append(CorpusNode(
            cve_id=cid,
            cvss_vector=cvss,
            cwe_ids=list(c.get("cwe_ids", []) or []),
            technical_impacts=impacts,
            description=c.get("description", "") or "",
            age_days=c.get("age_days"),
            modified_age_days=c.get("modified_age_days"),
            prereq_key=_canon_pairs(pres),
            outcome_key=_canon_pairs(outs),
            epss_score=c.get("epss_score"),
        ))

    ids = [n.cve_id for n in nodes]

    # enables edges: a -> b iff outcomes(a) satisfy prereqs(b)
    edges: List[CorpusEdge] = []
    self_loops = 0
    in_deg: Counter = Counter()
    out_deg: Counter = Counter()
    for a in ids:
        outs = node_outcomes[a]
        if not outs:
            continue  # a grants nothing -> enables nobody
        for b in ids:
            if not node_prereqs[b]:
                # b has no AV/PR prereqs -> trivially enabled by anyone with
                # outcomes; treat as an edge only when a actually grants
                # something (outs is non-empty, checked above)
                pass
            if enables(outs, node_prereqs[b]):
                if a == b:
                    self_loops += 1
                    if not include_self_loops:
                        continue
                edges.append(CorpusEdge(source=a, target=b))
                out_deg[a] += 1
                in_deg[b] += 1

    # diagnostics
    isolated = [cid for cid in ids if in_deg[cid] == 0 and out_deg[cid] == 0]
    quotient = Counter((n.prereq_key, n.outcome_key) for n in nodes)
    largest = [
        (f"{pk} => {ok}", cnt)
        for (pk, ok), cnt in quotient.most_common(10)
    ]
    diagnostics = CorpusDiagnostics(
        node_count=len(nodes),
        edge_count=len(edges),
        self_loop_count=self_loops,
        isolated_node_count=len(isolated),
        isolated_node_share=(len(isolated) / len(nodes)) if nodes else 0.0,
        quotient_class_count=len(quotient),
        largest_quotient_classes=largest,
        in_degree_histogram=_histogram([in_deg[c] for c in ids]),
        out_degree_histogram=_histogram([out_deg[c] for c in ids]),
        no_prereq_count=sum(1 for n in nodes if not node_prereqs[n.cve_id]),
        no_outcome_count=sum(1 for n in nodes if not node_outcomes[n.cve_id]),
    )

    return Corpus(
        schema_version=SCHEMA_VERSION,
        nodes=nodes,
        edges=edges,
        diagnostics=diagnostics,
        meta=meta or {},
    )
