"""GML-1 tests: label snapshot parsing/join, dataset encoding + grouped split,
metrics. Pure (no network, no GPU needed)."""

import gzip

import numpy as np

from ml.labels import _parse_csv_bytes, attach_labels, EpssSnapshot
from ml.dataset import build_dataset, grouped_split, assert_no_group_leak, FEATURE_NAMES
from ml.metrics import spearman, top_decile_precision, mae


SNAPSHOT_CSV = (
    "#model_version:v2026.06.15,score_date:2026-08-21T12:03:15Z\n"
    "cve,epss,percentile\n"
    "CVE-A,0.50000,0.90000\n"
    "CVE-B,0.01000,0.20000\n"
)


def test_parse_snapshot_header_and_rows():
    snap = _parse_csv_bytes(SNAPSHOT_CSV.encode())
    assert snap.model_version == "v2026.06.15"
    assert snap.score_date.startswith("2026-08-21")
    assert snap.get("CVE-A") == (0.5, 0.9)
    assert snap.get("cve-b") == (0.01, 0.2)   # case-insensitive
    assert len(snap) == 2


def _corpus():
    return {
        "graphs": [
            {"image": "img1", "nodes": [
                {"cve_id": "CVE-A", "chain_depth": 0, "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/C:H/I:H/A:H",
                 "av": "N", "pr": "N", "ac": "L", "ui": "N", "cwe_ids": ["CWE-79"], "epss_score": 0.0},
                {"cve_id": "CVE-B", "chain_depth": 1, "cvss_vector": "CVSS:3.1/AV:L/AC:H/PR:H/UI:R/C:L/I:L/A:N",
                 "av": "L", "pr": "H", "ac": "H", "ui": "R", "cwe_ids": ["CWE-89"], "epss_score": 0.0},
            ], "edges": [{"source": "CVE-A", "target": "CVE-B"}]},
            {"image": "img2", "nodes": [
                {"cve_id": "CVE-A", "chain_depth": 0, "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/C:H/I:H/A:H",
                 "av": "N", "pr": "N", "ac": "L", "ui": "N", "cwe_ids": ["CWE-79"], "epss_score": 0.0},
            ], "edges": []},
        ],
        "meta": {},
    }


def test_attach_labels_coverage_and_percentile():
    corpus = _corpus()
    snap = _parse_csv_bytes(SNAPSHOT_CSV.encode())
    rep = attach_labels(corpus, snap)
    assert rep.unique_cves == 2 and rep.labeled_cves == 2
    assert rep.total_nodes == 3 and rep.labeled_nodes == 3   # CVE-A twice + CVE-B
    # percentile written onto nodes
    a = corpus["graphs"][0]["nodes"][0]
    assert a["epss_percentile"] == 0.9
    assert corpus["meta"]["epss_snapshot"]["model_version"] == "v2026.06.15"


def test_missing_cve_is_unlabeled():
    corpus = _corpus()
    snap = EpssSnapshot("d", "v", {"CVE-A": (0.5, 0.9)})   # CVE-B missing
    rep = attach_labels(corpus, snap)
    assert "CVE-B" in rep.missing_cves
    b = corpus["graphs"][0]["nodes"][1]
    assert b["epss_percentile"] is None


def test_build_dataset_shapes_and_label():
    corpus = _corpus()
    attach_labels(corpus, _parse_csv_bytes(SNAPSHOT_CSV.encode()))
    ds = build_dataset(corpus)
    assert ds.X.shape == (3, len(FEATURE_NAMES))
    assert np.allclose(sorted(set(ds.y.tolist())), [0.2, 0.9], atol=1e-5)
    # CVE-A occurs in both images → group appears twice
    assert list(ds.groups).count("CVE-A") == 2


def test_build_dataset_drops_unlabeled():
    corpus = _corpus()
    attach_labels(corpus, EpssSnapshot("d", "v", {"CVE-A": (0.5, 0.9)}))
    ds = build_dataset(corpus)
    # only CVE-A rows survive (2), CVE-B dropped
    assert len(ds) == 2
    assert set(ds.cve_ids) == {"CVE-A"}


def test_grouped_split_no_leak():
    # many synthetic CVEs across two images
    graphs = []
    for img in ("i1", "i2"):
        nodes = []
        for k in range(40):
            nodes.append({
                "cve_id": f"CVE-{k}", "chain_depth": k % 2,
                "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/C:H/I:H/A:H",
                "av": "N", "pr": "N", "ac": "L", "ui": "N",
                "cwe_ids": ["CWE-1"], "epss_percentile": (k % 10) / 10.0,
            })
        graphs.append({"image": img, "nodes": nodes, "edges": []})
    ds = build_dataset({"graphs": graphs, "meta": {}})
    tr, va, te = grouped_split(ds, seed=0)
    assert_no_group_leak(ds, tr, va, te)      # must not raise
    assert len(tr) + len(va) + len(te) == len(ds)


def test_metrics_basic():
    y = np.array([0.1, 0.4, 0.9, 0.6])
    assert spearman(y, y) == 1.0
    assert top_decile_precision(y, y, q=0.75) == 1.0     # top-1 recovered
    assert mae(y, y) == 0.0


def test_pyg_batch_builder():
    # verify the GNN batch has per-image subgraphs and no cross-image edges
    import pytest
    pytest.importorskip("torch_geometric")
    from ml.gnn import build_pyg_batch
    corpus = {
        "graphs": [
            {"image": "i1", "nodes": [
                {"cve_id": "CVE-A", "chain_depth": 0, "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/C:H/I:H/A:H",
                 "av": "N", "pr": "N", "ac": "L", "ui": "N", "cwe_ids": ["CWE-1"], "epss_percentile": 0.9},
                {"cve_id": "CVE-B", "chain_depth": 1, "cvss_vector": "CVSS:3.1/AV:L/AC:L/PR:H/UI:N/C:H/I:H/A:H",
                 "av": "L", "pr": "H", "ac": "L", "ui": "N", "cwe_ids": ["CWE-2"], "epss_percentile": 0.3}],
             "edges": [{"source": "CVE-A", "target": "CVE-B"}]},
            {"image": "i2", "nodes": [
                {"cve_id": "CVE-C", "chain_depth": 0, "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/C:H/I:H/A:H",
                 "av": "N", "pr": "N", "ac": "L", "ui": "N", "cwe_ids": ["CWE-1"], "epss_percentile": 0.5}],
             "edges": []},
        ],
        "meta": {},
    }
    ds = build_dataset(corpus)
    batch = build_pyg_batch(ds, corpus, bidirectional=True)
    assert batch.num_nodes == 3
    # one contribution edge, bidirectional → 2 directed edges; no cross-image
    assert batch.num_edges == 2
