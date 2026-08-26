"""Pure attack-chain primitives shared by the graph builder and the Graph-ML
corpus exporter.

Two single-source-of-truth functions extracted so the builder
(`KnowledgeGraphBuilder`) and the ML exporter compute *identical* chains:

  * ``escalating_outcomes`` — the subset of a CVE's outcome Vector Changers
    that STRICTLY raise the attacker beyond the CVE's own prerequisites (the
    builder only accumulates these into ``available_vcs``; a PR:H outcome on a
    CVE that already required PR:H is not a new capability).
  * ``assign_chain_depths`` — the depth-layered BFS: starting from the
    attacker's baseline Vector Changers, repeatedly admit every CVE whose
    prerequisites are met, accumulate their escalating outcomes, and advance a
    depth. Monotonic accumulation (capability is never lost) is what makes the
    chain a DAG.

Both rely on ``consensual_matrix.prereqs_satisfied`` for the gating decision,
so the enabling predicate lives in exactly one place.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from src.core.consensual_matrix import (
    AV_HIERARCHY,
    PR_HIERARCHY,
    prereqs_satisfied,
)

VC = Tuple[str, str]

# The Layer-1 attacker baseline used by the builder: reachable over the
# network, holding no privileges. Every chain starts here.
DEFAULT_INITIAL_VCS: Set[VC] = {("AV", "N"), ("PR", "N")}


def _level(vc_type: str, value: str) -> int:
    if vc_type == "AV":
        return AV_HIERARCHY.get(value, 0)
    if vc_type == "PR":
        return PR_HIERARCHY.get(value, 0)
    return 0


def escalating_outcomes(prereqs: Iterable[VC], outcomes: Iterable[VC]) -> Set[VC]:
    """Outcomes that strictly escalate the attacker beyond ``prereqs``.

    Mirrors the builder's per-impact ``is_escalation`` test exactly:
      * AV / PR outcome is kept iff its level exceeds the CVE's prereq level
        of the same type (default prereq level 0 when absent);
      * every other outcome type (EX, and any future type) is always kept.
    """
    prereq_level: Dict[str, int] = {}
    for t, v in prereqs:
        if t in ("AV", "PR"):
            prereq_level[t] = _level(t, v)

    kept: Set[VC] = set()
    for t, v in outcomes:
        if t in ("AV", "PR"):
            if _level(t, v) > prereq_level.get(t, 0):
                kept.add((t, v))
        else:
            kept.add((t, v))
    return kept


def contributes(enabler_outcomes: Iterable[VC], target_prereqs: Iterable[VC]) -> bool:
    """Does an enabler's (escalating) outcomes satisfy at least one AV/PR
    prerequisite of a target CVE?

    Used to draw CVE->CVE contribution edges: ``a -> b`` when a supplies a
    capability b requires. Weaker than full prereq satisfaction (b's remaining
    prereqs may be met by the baseline or other predecessors) — an edge marks
    a genuine contribution, not sole sufficiency.
    """
    avail = set(enabler_outcomes)
    for t, vreq in target_prereqs:
        if t not in ("AV", "PR"):
            continue
        need = _level(t, vreq)
        if any(t2 == t and _level(t2, v2) >= need for t2, v2 in avail):
            return True
    return False


def assign_chain_depths(
    entries: Sequence[Dict[str, object]],
    initial_vcs: Optional[Set[VC]] = None,
    max_depth: int = 10,
) -> Dict[int, Optional[int]]:
    """Assign each CVE its attack-chain depth via the builder's BFS.

    Args:
        entries: sequence of dicts, each with:
            ``prereqs``  — list[VC] (the CVE's AV/PR prerequisites)
            ``outcomes`` — list[VC] (the CVE's raw post-exploitation VCs)
        initial_vcs: attacker baseline (default: network reach, no privileges).
        max_depth: safety cap on chain length.

    Returns:
        {index: depth} where depth 0 = exploitable from baseline, depth d =
        first reachable after d rounds of prior exploitation, or ``None`` if
        the CVE is never reachable in this scenario.
    """
    available: Set[VC] = set(initial_vcs if initial_vcs is not None else DEFAULT_INITIAL_VCS)
    depths: Dict[int, Optional[int]] = {}
    unprocessed: List[int] = list(range(len(entries)))
    depth = 0

    while unprocessed and depth <= max_depth:
        newly: List[int] = []
        still: List[int] = []
        for i in unprocessed:
            prereqs = entries[i]["prereqs"]  # type: ignore[index]
            if prereqs_satisfied(prereqs, available):  # type: ignore[arg-type]
                depths[i] = depth
                newly.append(i)
            else:
                still.append(i)

        if not newly:
            break

        for i in newly:
            available |= escalating_outcomes(
                entries[i]["prereqs"], entries[i]["outcomes"]  # type: ignore[arg-type]
            )
        unprocessed = still
        depth += 1

    for i in unprocessed:
        depths[i] = None  # unreachable in this scenario
    return depths
