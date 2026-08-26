"""GML-0 corpus-exporter tests (Graph-ML EPSS plan, per-image DAG version).

Pure unit tests on synthetic mini-corpora — no Mongo, no network, no graph
instance. Verifies: per-image DAG construction, depth-layered chaining,
contribution edges, acyclicity, feature extraction (incl. categorical AC/UI),
label separation, and diagnostics.
"""

from ml.exporter import (
    build_corpus,
    build_image_graph,
    outcomes_of,
    prereqs_of,
    parse_cvss_components,
    SCHEMA_VERSION,
)


CVSS_NET_NOPRIV = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
CVSS_LOCAL_HIGHPRIV = "CVSS:3.1/AV:L/AC:H/PR:H/UI:R/S:U/C:H/I:H/A:H"
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


# --- helpers ----------------------------------------------------------------

def test_outcomes_union_over_impacts():
    outs = outcomes_of([IMPACT_RCE, IMPACT_READ])
    assert ("AV", "L") in outs and ("PR", "H") in outs and ("EX", "Y") in outs


def test_prereqs_from_cvss():
    assert ("AV", "L") in prereqs_of(CVSS_LOCAL_HIGHPRIV)
    assert ("PR", "H") in prereqs_of(CVSS_LOCAL_HIGHPRIV)


def test_parse_cvss_components_includes_environmental():
    comps = parse_cvss_components(CVSS_LOCAL_HIGHPRIV)
    assert comps["AV"] == "L" and comps["PR"] == "H"
    assert comps["AC"] == "H" and comps["UI"] == "R"   # environmental VCs


# --- per-image graph --------------------------------------------------------

def test_depth_layers_and_contribution_edge():
    # A: network/no-priv RCE (depth 0, grants AV:L,PR:H,EX:Y)
    # B: needs local+high-priv (depth 1) → A contributes to B
    g = build_image_graph("img", [
        _cve("CVE-A", CVSS_NET_NOPRIV, [IMPACT_RCE]),
        _cve("CVE-B", CVSS_LOCAL_HIGHPRIV, [IMPACT_READ]),
    ])
    depth = {n.cve_id: n.chain_depth for n in g.nodes}
    assert depth["CVE-A"] == 0
    assert depth["CVE-B"] == 1
    pairs = {(e.source, e.target) for e in g.edges}
    assert ("CVE-A", "CVE-B") in pairs
    assert ("CVE-B", "CVE-A") not in pairs   # DAG: no back edge


def test_layer_skipping_contribution():
    # Chain of 3 where CVE1 (depth 0) also directly contributes to CVE3.
    # A grants AV:L (depth 0). B needs AV:L, grants PR:H (depth 1).
    # C needs AV:L AND PR:H (depth 2). A supplies AV:L → A→C edge (skip).
    g = build_image_graph("img", [
        _cve("A", "CVSS:3.1/AV:N/AC:L/PR:N/UI:N", [IMPACT_READ]),           # →AV:L
        _cve("B", "CVSS:3.1/AV:L/AC:L/PR:N/UI:N", [IMPACT_RCE]),            # →AV:L,PR:H,EX:Y
        _cve("C", "CVSS:3.1/AV:L/AC:L/PR:H/UI:N", [IMPACT_DOS]),            # needs AV:L+PR:H
    ])
    depth = {n.cve_id: n.chain_depth for n in g.nodes}
    assert depth["A"] == 0 and depth["B"] == 1 and depth["C"] == 2
    pairs = {(e.source, e.target) for e in g.edges}
    assert ("A", "C") in pairs   # layer-skipping contribution (A's AV:L helps C)
    assert ("B", "C") in pairs


def test_unreachable_node_is_isolated():
    # Physical-access CVE is never reachable from the network baseline.
    g = build_image_graph("img", [
        _cve("CVE-A", CVSS_NET_NOPRIV, [IMPACT_RCE]),
        _cve("CVE-P", CVSS_PHYSICAL, [IMPACT_DOS]),
    ])
    depth = {n.cve_id: n.chain_depth for n in g.nodes}
    assert depth["CVE-P"] is None
    assert g.unreachable_count == 1
    # no edge touches the unreachable node
    assert all("CVE-P" not in (e.source, e.target) for e in g.edges)


def test_features_and_label_separation():
    g = build_image_graph("img", [_cve("CVE-A", CVSS_LOCAL_HIGHPRIV, [IMPACT_RCE], epss=0.42)])
    n = g.nodes[0]
    assert n.epss_score == 0.42           # label present
    assert n.ac == "H" and n.ui == "R"    # environmental VCs as categorical features
    d = n.to_dict()
    assert "epss" not in d["cvss_vector"]  # label never leaks into a feature


# --- corpus (set of image graphs) ------------------------------------------

def test_corpus_is_set_of_dags():
    corpus = build_corpus({
        "nginx": [_cve("CVE-A", CVSS_NET_NOPRIV, [IMPACT_RCE]),
                  _cve("CVE-B", CVSS_LOCAL_HIGHPRIV, [IMPACT_READ])],
        "redis": [_cve("CVE-A", CVSS_NET_NOPRIV, [IMPACT_RCE]),
                  _cve("CVE-C", CVSS_PHYSICAL, [IMPACT_DOS])],
    })
    assert corpus.schema_version == SCHEMA_VERSION
    assert corpus.diagnostics.image_count == 2
    assert corpus.diagnostics.all_dags is True
    # CVE-A appears in BOTH image graphs (natural; split must group by cve id)
    assert corpus.diagnostics.unique_cves == 3        # A, B, C
    assert corpus.diagnostics.total_nodes == 4        # A,B (nginx) + A,C (redis)


def test_same_cve_in_multiple_images():
    corpus = build_corpus({
        "img1": [_cve("CVE-X", CVSS_NET_NOPRIV, [IMPACT_RCE])],
        "img2": [_cve("CVE-X", CVSS_NET_NOPRIV, [IMPACT_RCE])],
    })
    occurrences = [n for g in corpus.graphs for n in g.nodes if n.cve_id == "CVE-X"]
    assert len(occurrences) == 2                      # one per image
    assert corpus.diagnostics.unique_cves == 1


def test_dedupe_within_image():
    g = build_image_graph("img", [
        _cve("CVE-A", CVSS_NET_NOPRIV, [IMPACT_RCE]),
        _cve("CVE-A@pkg2", CVSS_NET_NOPRIV, [IMPACT_RCE]),   # same CVE, another pkg
    ])
    assert len([n for n in g.nodes if n.cve_id == "CVE-A"]) == 1


def test_export_is_deterministic():
    images = {"img": [_cve("CVE-A", CVSS_NET_NOPRIV, [IMPACT_RCE]),
                      _cve("CVE-B", CVSS_LOCAL_HIGHPRIV, [IMPACT_READ])]}
    assert build_corpus(images).to_dict() == build_corpus(images).to_dict()


def test_empty_corpus():
    corpus = build_corpus({})
    assert corpus.diagnostics.image_count == 0
    assert corpus.diagnostics.total_nodes == 0
    assert corpus.diagnostics.all_dags is True


# --- diagnostics math (ml/diagnose.py) --------------------------------------

def test_spearman_monotonic_and_ties():
    from ml.diagnose import spearman
    assert abs(spearman([1, 2, 3, 4], [1, 4, 9, 16]) - 1.0) < 1e-9
    assert abs(spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1.0) < 1e-9
    import math
    assert math.isnan(spearman([1, 1, 1, 1], [1, 2, 3, 4]))


def test_eta_squared_separates_groups():
    from ml.diagnose import eta_squared
    assert abs(eta_squared({"a": [1.0, 1.0], "b": [5.0, 5.0]}) - 1.0) < 1e-9
    assert abs(eta_squared({"a": [1.0, 3.0], "b": [1.0, 3.0]})) < 1e-9
