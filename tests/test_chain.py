"""Tests for the shared attack-chain primitives (src/core/chain.py).

These lock the depth-BFS, the escalation filter, and the contribution
predicate that both the graph builder and the Graph-ML exporter rely on.
The builder now calls escalating_outcomes / prereqs_satisfied for its own
accumulation and gating, so these primitives are the single source of truth.
"""

from src.core.chain import (
    escalating_outcomes,
    contributes,
    assign_chain_depths,
    DEFAULT_INITIAL_VCS,
)


# --- escalating_outcomes ----------------------------------------------------

def test_escalation_requires_strict_level_gain():
    # prereq PR:H, outcome PR:H → NOT escalation (no new capability)
    assert ("PR", "H") not in escalating_outcomes([("PR", "H")], [("PR", "H")])
    # prereq PR:N, outcome PR:H → escalation
    assert ("PR", "H") in escalating_outcomes([("PR", "N")], [("PR", "H")])


def test_ex_and_other_types_always_escalate():
    assert ("EX", "Y") in escalating_outcomes([("PR", "H")], [("EX", "Y")])


def test_av_escalation_uses_hierarchy():
    # prereq AV:N (0), outcome AV:L (2) → escalation
    assert ("AV", "L") in escalating_outcomes([("AV", "N")], [("AV", "L")])
    # prereq AV:L (2), outcome AV:N (0) → not escalation
    assert ("AV", "N") not in escalating_outcomes([("AV", "L")], [("AV", "N")])


# --- contributes ------------------------------------------------------------

def test_contributes_when_outcome_meets_a_prereq():
    # enabler grants AV:L + PR:H; target needs AV:L → contributes
    assert contributes({("AV", "L"), ("PR", "H")}, [("AV", "L")]) is True


def test_no_contribution_when_type_absent():
    # enabler grants only AV:L; target needs PR:H → no PR granted → no edge
    assert contributes({("AV", "L")}, [("PR", "H")]) is False


def test_contribution_respects_hierarchy():
    # enabler grants PR:H (2); target needs PR:L (1) → 2>=1 contributes
    assert contributes({("PR", "H")}, [("PR", "L")]) is True
    # enabler grants PR:L (1); target needs PR:H (2) → 1>=2 false
    assert contributes({("PR", "L")}, [("PR", "H")]) is False


# --- assign_chain_depths ----------------------------------------------------

def _entry(prereqs, outcomes):
    return {"prereqs": prereqs, "outcomes": outcomes}


def test_depth_layers_accumulate():
    # CVE0: exploitable from baseline, grants full local+high-priv compromise
    # CVE1: needs AV:L + PR:H → only reachable after CVE0
    # CVE2: needs AV:P (physical) → never reachable in the network scenario
    entries = [
        _entry([("AV", "N"), ("PR", "N")], [("AV", "L"), ("PR", "H"), ("EX", "Y")]),
        _entry([("AV", "L"), ("PR", "H")], [("EX", "Y")]),
        _entry([("AV", "P"), ("PR", "N")], []),
    ]
    depths = assign_chain_depths(entries)
    assert depths[0] == 0
    assert depths[1] == 1
    assert depths[2] is None   # unreachable


def test_baseline_seeds_depth_zero():
    # A CVE needing exactly the baseline (AV:N, PR:N) is depth 0.
    entries = [_entry([("AV", "N"), ("PR", "N")], [("EX", "Y")])]
    assert assign_chain_depths(entries)[0] == 0


def test_no_outcomes_means_no_further_reach():
    # CVE0 reachable but grants nothing escalating; CVE1 needs PR:H → stuck.
    entries = [
        _entry([("AV", "N"), ("PR", "N")], []),          # depth 0, grants nothing
        _entry([("AV", "N"), ("PR", "H")], [("EX", "Y")]),  # needs PR:H, never gained
    ]
    depths = assign_chain_depths(entries)
    assert depths[0] == 0
    assert depths[1] is None


def test_default_baseline_is_network_no_privs():
    assert DEFAULT_INITIAL_VCS == {("AV", "N"), ("PR", "N")}
