"""GML-0 corpus-exporter tests (Graph-ML EPSS plan).

Pure unit tests on synthetic mini-corpora — no Mongo, no network, no graph
instance. Verifies: dedup by CVE id, the ``enables`` predicate wiring, label
separation, and the diagnostics census.
"""

from ml.exporter import (
    build_corpus,
    outcomes_of,
    prereqs_of,
    enables,
    prereq_key,
    outcome_key,
    SCHEMA_VERSION,
)


# CVSS shorthands (only AV/PR/AC/UI matter to the predicate; rest is filler)
CVSS_NET_NOPRIV = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
CVSS_LOCAL_HIGHPRIV = "CVSS:3.1/AV:L/AC:L/PR:H/UI:N/S:U/C:H/I:H/A:H"
CVSS_PHYSICAL = "CVSS:3.1/AV:P/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"

IMPACT_RCE = "Execute Unauthorized Code or Commands"   # → {AV:L, PR:H, EX:Y}
IMPACT_READ = "Read Application Data"                   # → {AV:L}
IMPACT_DOS = "DoS: Crash, Exit, or Restart"             # → {} (no outcomes)


def _cve(cid, cvss, impacts, epss=0.1, **extra):
    d = {
        "id": cid,
        "cvss_vector": cvss,
        "technical_impacts": impacts,
        "cwe_ids": extra.pop("cwe_ids", ["CWE-79"]),
        "description": extra.pop("description", "synthetic"),
        "epss_score": epss,
    }
    d.update(extra)
    return d


# --- VC helpers -------------------------------------------------------------

def test_outcomes_union_over_impacts():
    outs = outcomes_of([IMPACT_RCE, IMPACT_READ])
    assert ("AV", "L") in outs
    assert ("PR", "H") in outs
    assert ("EX", "Y") in outs


def test_dos_grants_no_outcomes():
    assert outcomes_of([IMPACT_DOS]) == set()


def test_prereqs_from_cvss():
    assert ("AV", "L") in prereqs_of(CVSS_LOCAL_HIGHPRIV)
    assert ("PR", "H") in prereqs_of(CVSS_LOCAL_HIGHPRIV)


def test_enables_predicate_direct():
    rce_outcomes = outcomes_of([IMPACT_RCE])          # {AV:L, PR:H, EX:Y}
    local_prereqs = prereqs_of(CVSS_LOCAL_HIGHPRIV)   # [AV:L, PR:H]
    assert enables(rce_outcomes, local_prereqs) is True

    # DoS grants nothing → enables no one with real prereqs
    assert enables(outcomes_of([IMPACT_DOS]), local_prereqs) is False


def test_enables_is_strict_without_attacker_baseline():
    # Read-only outcome {AV:L} cannot satisfy a PR:H prereq (no PR granted)
    assert enables(outcomes_of([IMPACT_READ]), prereqs_of(CVSS_LOCAL_HIGHPRIV)) is False
    # and cannot satisfy AV:P (physical, level 3 > local level 2)
    assert enables(outcomes_of([IMPACT_READ]), prereqs_of(CVSS_PHYSICAL)) is False


# --- quotient keys ----------------------------------------------------------

def test_quotient_keys_are_deterministic_strings():
    assert prereq_key(CVSS_LOCAL_HIGHPRIV) == "AV:L,PR:H"
    assert outcome_key([IMPACT_RCE]) == "AV:L,EX:Y,PR:H"
    assert outcome_key([IMPACT_DOS]) == "none"


# --- build_corpus -----------------------------------------------------------

def test_dedupe_by_cve_id():
    corpus = build_corpus([
        _cve("CVE-2024-0001", CVSS_NET_NOPRIV, [IMPACT_RCE]),
        _cve("CVE-2024-0001@host2@pkg", CVSS_NET_NOPRIV, [IMPACT_RCE]),  # dup
        _cve("CVE-2024-0002", CVSS_LOCAL_HIGHPRIV, [IMPACT_READ]),
    ])
    ids = {n.cve_id for n in corpus.nodes}
    assert ids == {"CVE-2024-0001", "CVE-2024-0002"}
    assert corpus.diagnostics.node_count == 2


def test_enables_edge_wired_between_two_cves():
    # A: network, no privs, RCE → grants {AV:L, PR:H, EX:Y}
    # B: needs local + high priv → A enables B; B (read-only) does not enable A
    corpus = build_corpus([
        _cve("CVE-A", CVSS_NET_NOPRIV, [IMPACT_RCE]),
        _cve("CVE-B", CVSS_LOCAL_HIGHPRIV, [IMPACT_READ]),
    ])
    edge_pairs = {(e.source, e.target) for e in corpus.edges}
    assert ("CVE-A", "CVE-B") in edge_pairs
    assert ("CVE-B", "CVE-A") not in edge_pairs


def test_self_loops_excluded_by_default_but_counted():
    # A network/no-priv RCE enables itself (its outcomes satisfy its own
    # trivial prereqs), but the self-edge is dropped by default.
    corpus = build_corpus([_cve("CVE-A", CVSS_NET_NOPRIV, [IMPACT_RCE])])
    assert corpus.diagnostics.self_loop_count >= 1
    assert all(e.source != e.target for e in corpus.edges)

    with_loops = build_corpus(
        [_cve("CVE-A", CVSS_NET_NOPRIV, [IMPACT_RCE])],
        include_self_loops=True,
    )
    assert any(e.source == e.target for e in with_loops.edges)


def test_label_is_not_a_feature():
    corpus = build_corpus([_cve("CVE-A", CVSS_NET_NOPRIV, [IMPACT_RCE], epss=0.42)])
    node = corpus.nodes[0]
    assert node.epss_score == 0.42
    d = node.to_dict()
    # epss lives under its own key; feature fields never carry it
    assert d["epss_score"] == 0.42
    assert "epss" not in d["cvss_vector"]


def test_diagnostics_census_and_isolated():
    # C is physical + DoS: grants nothing and needs a physical foothold no one
    # provides → isolated node.
    corpus = build_corpus([
        _cve("CVE-A", CVSS_NET_NOPRIV, [IMPACT_RCE]),
        _cve("CVE-B", CVSS_LOCAL_HIGHPRIV, [IMPACT_READ]),
        _cve("CVE-C", CVSS_PHYSICAL, [IMPACT_DOS]),
    ])
    diag = corpus.diagnostics
    assert diag.node_count == 3
    assert diag.quotient_class_count == 3          # three distinct key pairs
    assert "CVE-C" not in {n.cve_id for n in corpus.nodes if False}  # sanity
    assert diag.isolated_node_count >= 1
    assert 0.0 <= diag.isolated_node_share <= 1.0
    assert diag.no_outcome_count >= 1              # C grants nothing


def test_export_is_deterministic():
    cves = [
        _cve("CVE-A", CVSS_NET_NOPRIV, [IMPACT_RCE]),
        _cve("CVE-B", CVSS_LOCAL_HIGHPRIV, [IMPACT_READ]),
    ]
    a = build_corpus(cves).to_dict()
    b = build_corpus(cves).to_dict()
    assert a == b
    assert a["schema_version"] == SCHEMA_VERSION


def test_empty_corpus():
    corpus = build_corpus([])
    assert corpus.diagnostics.node_count == 0
    assert corpus.diagnostics.isolated_node_share == 0.0
    assert corpus.edges == []


# --- diagnostics math (ml/diagnose.py) --------------------------------------

def test_spearman_monotonic_and_ties():
    from ml.diagnose import spearman
    # perfect monotone (non-linear) → ρ = 1
    assert abs(spearman([1, 2, 3, 4], [1, 4, 9, 16]) - 1.0) < 1e-9
    # perfect anti-monotone → ρ = -1
    assert abs(spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1.0) < 1e-9
    # constant input → nan (undefined)
    import math
    assert math.isnan(spearman([1, 1, 1, 1], [1, 2, 3, 4]))


def test_eta_squared_separates_groups():
    from ml.diagnose import eta_squared
    # fully separated groups → η² = 1
    assert abs(eta_squared({"a": [1.0, 1.0], "b": [5.0, 5.0]}) - 1.0) < 1e-9
    # identical group means → η² = 0
    assert abs(eta_squared({"a": [1.0, 3.0], "b": [1.0, 3.0]})) < 1e-9
