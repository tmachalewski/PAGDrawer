"""GML-0 — Corpus exporter for the Graph-ML EPSS prediction task.

Builds the ML corpus described in `Docs/Plans/GraphML_EPSS_Prediction.md`,
revised 2026-08-26 to match the confirmed vision:

  * The corpus is a **set of per-Docker-image DAGs** — one graph per scanned
    image. Chaining happens ONLY between vulnerabilities that co-occur on the
    same image (reality-pruning). The same CVE may appear in several image
    graphs; that is expected and handled by a group-wise train/val/test split
    on ``original_cve``.
  * Each image graph is built with the builder's chain logic
    (``core.chain.assign_chain_depths``): the attacker starts from the
    baseline Vector Changers, prerequisites gate reachability, escalating
    outcomes accumulate, depth increases → a Directed Acyclic Graph.
  * **Fixed maximal scenario**: attacker skill and user interaction are set so
    every CVE that can ever chain is reachable (the AV/PR baseline BFS already
    does this; the AC/UI scenario gate is a separate frontend overlay and is
    NOT applied here). AC/UI therefore stay as per-node *features*.
  * **Edges** are CVE->CVE contribution edges: ``a -> b`` when depth(a) <
    depth(b) and a's escalating outcomes supply a Vector Changer that b's
    prerequisites require (layer-skipping allowed — a depth-0 CVE can
    contribute to a depth-2 CVE, matching "VCs from CVE1 enable CVE3").
  * **Features** are raw/categorical per CVE (CVSS components incl. AC/UI,
    CWE, technical impacts, description, age); EPSS rides along as the label,
    never a feature.

The core (`build_corpus`) is pure: plain dicts in, plain data out — unit
tested on synthetic mini-corpora without Mongo, network, or a graph instance.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from src.core.consensual_matrix import extract_prerequisites, get_post_exploitation_vcs
from src.core.chain import (
    assign_chain_depths,
    escalating_outcomes,
    contributes,
    DEFAULT_INITIAL_VCS,
)

# Bump only on breaking changes to the exported JSON shape.
SCHEMA_VERSION = 2  # v2: per-image DAGs (v1 was the flat global closure)


# =============================================================================
# VC / CVSS helpers
# =============================================================================

def outcomes_of(technical_impacts: Sequence[str]) -> Set[Tuple[str, str]]:
    """Union of Vector-Changer outcomes over a CVE's technical impacts."""
    out: Set[Tuple[str, str]] = set()
    for impact in technical_impacts or []:
        out.update(get_post_exploitation_vcs(impact))
    return out


def prereqs_of(cvss_vector: str) -> List[Tuple[str, str]]:
    """Chain prerequisites (AV/PR) extracted from a CVE's CVSS vector."""
    return extract_prerequisites(cvss_vector)


def parse_cvss_components(cvss_vector: str) -> Dict[str, str]:
    """Split a CVSS vector into its component map (AV, AC, PR, UI, C, I, A…)."""
    comps: Dict[str, str] = {}
    for part in (cvss_vector or "").split("/"):
        if ":" in part:
            k, v = part.split(":", 1)
            comps[k] = v
    return comps


# =============================================================================
# Corpus data classes
# =============================================================================

@dataclass
class CorpusNode:
    """One CVE occurrence inside one image graph.

    The same ``cve_id`` may appear as a node in multiple image graphs; the
    global label/features are identical, only ``chain_depth`` (its role in
    that image's chain) can differ.
    """
    cve_id: str
    image: str
    chain_depth: Optional[int]
    # --- features (raw / categorical) ---
    cvss_vector: str
    av: str = ""          # Attack Vector (state VC prereq)
    pr: str = ""          # Privileges Required (state VC prereq)
    ac: str = ""          # Attack Complexity (environmental — attacker skill)
    ui: str = ""          # User Interaction (environmental — user cooperation)
    cwe_ids: List[str] = field(default_factory=list)
    technical_impacts: List[str] = field(default_factory=list)
    description: str = ""
    age_days: Optional[int] = None
    modified_age_days: Optional[int] = None
    prereq_key: str = ""
    outcome_key: str = ""
    # --- label (never a feature) ---
    epss_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CorpusEdge:
    source: str  # cve_id of the contributor (lower depth)
    target: str  # cve_id it helps enable (higher depth)

    def to_dict(self) -> Dict[str, str]:
        return {"source": self.source, "target": self.target}


@dataclass
class ImageGraph:
    """A single per-image DAG."""
    image: str
    nodes: List[CorpusNode]
    edges: List[CorpusEdge]
    reachable_count: int          # nodes with a finite chain_depth
    unreachable_count: int        # nodes never reachable in the scenario
    max_depth: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image": self.image,
            "reachable_count": self.reachable_count,
            "unreachable_count": self.unreachable_count,
            "max_depth": self.max_depth,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }


@dataclass
class CorpusDiagnostics:
    image_count: int
    total_nodes: int              # node occurrences across all image graphs
    unique_cves: int              # distinct original_cve
    total_edges: int
    all_dags: bool                # every image graph is acyclic (must be True)
    depth_histogram: Dict[int, int]      # chain_depth → node occurrences
    nodes_per_image: Dict[str, int]
    edges_per_image: Dict[str, int]
    unreachable_share: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Corpus:
    schema_version: int
    graphs: List[ImageGraph]
    diagnostics: CorpusDiagnostics
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "meta": self.meta,
            "diagnostics": self.diagnostics.to_dict(),
            "graphs": [g.to_dict() for g in self.graphs],
        }


# =============================================================================
# Build
# =============================================================================

def _canon_pairs(pairs) -> str:
    if not pairs:
        return "none"
    return ",".join(f"{t}:{v}" for t, v in sorted(set(pairs)))


def _norm_cve_id(raw: str) -> str:
    return (raw or "").split("@")[0].upper()


def _dedupe_within_image(cve_dicts: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One entry per CVE id within a single image (a CVE can be reported on
    several packages of the same image; the label-relevant fields are equal,
    so first occurrence wins)."""
    seen: Set[str] = set()
    out: List[Dict[str, Any]] = []
    for c in cve_dicts:
        cid = _norm_cve_id(c.get("id", ""))
        if not cid or cid in seen:
            continue
        seen.add(cid)
        out.append(c)
    return out


def build_image_graph(
    image: str,
    cve_dicts: Sequence[Dict[str, Any]],
    initial_vcs: Optional[Set[Tuple[str, str]]] = None,
) -> ImageGraph:
    """Build one per-image DAG from that image's enriched CVE dicts."""
    deduped = _dedupe_within_image(cve_dicts)

    # precompute prereqs / raw outcomes / escalating outcomes per CVE
    prereqs: Dict[str, List[Tuple[str, str]]] = {}
    raw_out: Dict[str, Set[Tuple[str, str]]] = {}
    esc_out: Dict[str, Set[Tuple[str, str]]] = {}
    order: List[str] = []
    for c in deduped:
        cid = _norm_cve_id(c["id"])
        p = prereqs_of(c.get("cvss_vector", "") or "")
        o = outcomes_of(c.get("technical_impacts", []) or [])
        prereqs[cid] = p
        raw_out[cid] = o
        esc_out[cid] = escalating_outcomes(p, o)
        order.append(cid)

    # depth-layered BFS (shared with the builder)
    entries = [{"prereqs": prereqs[cid], "outcomes": raw_out[cid]} for cid in order]
    depth_by_idx = assign_chain_depths(entries, initial_vcs=initial_vcs)
    depth: Dict[str, Optional[int]] = {order[i]: depth_by_idx[i] for i in range(len(order))}

    # nodes
    nodes: List[CorpusNode] = []
    by_id: Dict[str, Dict[str, Any]] = {_norm_cve_id(c["id"]): c for c in deduped}
    for cid in order:
        c = by_id[cid]
        comps = parse_cvss_components(c.get("cvss_vector", "") or "")
        nodes.append(CorpusNode(
            cve_id=cid,
            image=image,
            chain_depth=depth[cid],
            cvss_vector=c.get("cvss_vector", "") or "",
            av=comps.get("AV", ""),
            pr=comps.get("PR", ""),
            ac=comps.get("AC", ""),
            ui=comps.get("UI", ""),
            cwe_ids=list(c.get("cwe_ids", []) or []),
            technical_impacts=list(c.get("technical_impacts", []) or []),
            description=c.get("description", "") or "",
            age_days=c.get("age_days"),
            modified_age_days=c.get("modified_age_days"),
            prereq_key=_canon_pairs(prereqs[cid]),
            outcome_key=_canon_pairs(raw_out[cid]),
            epss_score=c.get("epss_score"),
        ))

    # contribution edges: a -> b when depth(a) < depth(b) and a's escalating
    # outcomes supply a VC that b's prereqs require. Layer-skipping allowed.
    edges: List[CorpusEdge] = []
    reachable = [cid for cid in order if depth[cid] is not None]
    for b in reachable:
        db = depth[b]
        if db == 0:
            continue  # depth-0 CVEs are sources (met by baseline)
        for a in reachable:
            if depth[a] is None or depth[a] >= db:
                continue
            if contributes(esc_out[a], prereqs[b]):
                edges.append(CorpusEdge(source=a, target=b))

    depths_finite = [d for d in depth.values() if d is not None]
    return ImageGraph(
        image=image,
        nodes=nodes,
        edges=edges,
        reachable_count=len(reachable),
        unreachable_count=len(order) - len(reachable),
        max_depth=max(depths_finite) if depths_finite else 0,
    )


def build_corpus(
    images: Dict[str, Sequence[Dict[str, Any]]],
    *,
    initial_vcs: Optional[Set[Tuple[str, str]]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Corpus:
    """Build the full corpus — one DAG per image.

    Args:
        images: mapping ``image_name -> [enriched CVE dicts]``. Each CVE dict
            needs ``id`` and ``cvss_vector``; optional ``technical_impacts``,
            ``cwe_ids``, ``description``, ``epss_score``, ``age_days``,
            ``modified_age_days``.
        initial_vcs: attacker baseline (default: network reach, no privileges —
            the fixed maximal scenario for AV/PR).
        meta: provenance copied verbatim into the export.
    """
    graphs = [
        build_image_graph(name, cves, initial_vcs=initial_vcs)
        for name, cves in images.items()
    ]

    # diagnostics
    total_nodes = sum(len(g.nodes) for g in graphs)
    total_edges = sum(len(g.edges) for g in graphs)
    unique = {n.cve_id for g in graphs for n in g.nodes}
    depth_hist: Counter = Counter()
    unreachable = 0
    for g in graphs:
        for n in g.nodes:
            if n.chain_depth is None:
                unreachable += 1
            else:
                depth_hist[n.chain_depth] += 1

    # acyclicity check (contribution edges have strictly increasing depth, so
    # this must hold; we verify rather than assume)
    all_dags = _verify_all_dags(graphs)

    diagnostics = CorpusDiagnostics(
        image_count=len(graphs),
        total_nodes=total_nodes,
        unique_cves=len(unique),
        total_edges=total_edges,
        all_dags=all_dags,
        depth_histogram=dict(sorted(depth_hist.items())),
        nodes_per_image={g.image: len(g.nodes) for g in graphs},
        edges_per_image={g.image: len(g.edges) for g in graphs},
        unreachable_share=(unreachable / total_nodes) if total_nodes else 0.0,
    )
    return Corpus(
        schema_version=SCHEMA_VERSION,
        graphs=graphs,
        diagnostics=diagnostics,
        meta=meta or {},
    )


def _verify_all_dags(graphs: Sequence[ImageGraph]) -> bool:
    """Confirm every image graph is acyclic via depth monotonicity of edges."""
    for g in graphs:
        depth = {n.cve_id: n.chain_depth for n in g.nodes}
        for e in g.edges:
            ds, dt = depth.get(e.source), depth.get(e.target)
            if ds is None or dt is None or ds >= dt:
                return False
    return True
