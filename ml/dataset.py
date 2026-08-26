"""GML-1 — feature matrix + grouped split for the per-image DAG corpus.

Turns the exported corpus (a set of per-image DAGs, each node an enriched CVE
occurrence with an EPSS percentile label) into arrays the rungs consume, and
provides the D22 grouped split (group = ``original_cve``, so a CVE that occurs
in several image graphs lands entirely in one fold — no label leakage).

Feature encoding is deliberately simple and tabular (rung 1/2 share it):
  * CVSS state components AV, PR (+ C, I, A) — one-hot
  * environmental VCs AC, UI — one-hot categorical (D21, never numeric)
  * chain_depth — the chain-position signal (small int; unreachable → -1)
  * in/out degree within the CVE's image graph — light structural context
  * CWE — hashed multi-hot (small dim, corpus is small)

The label is the EPSS **percentile** (D15). Rows without a percentile
(CVE absent from the snapshot) are dropped.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

# One-hot vocabularies for CVSS components (fixed order → stable columns).
AV_VALUES = ["N", "A", "L", "P"]
PR_VALUES = ["N", "L", "H"]
AC_VALUES = ["L", "H"]
UI_VALUES = ["N", "R"]
CIA_VALUES = ["N", "L", "H"]
CWE_HASH_DIM = 32


def _onehot(value: str, vocab: Sequence[str]) -> List[float]:
    return [1.0 if value == v else 0.0 for v in vocab]


def _cwe_hash(cwe_ids: Sequence[str], dim: int = CWE_HASH_DIM) -> List[float]:
    vec = [0.0] * dim
    for c in cwe_ids or []:
        vec[hash(c) % dim] = 1.0
    return vec


FEATURE_NAMES: List[str] = (
    [f"AV={v}" for v in AV_VALUES]
    + [f"PR={v}" for v in PR_VALUES]
    + [f"AC={v}" for v in AC_VALUES]
    + [f"UI={v}" for v in UI_VALUES]
    + [f"C={v}" for v in CIA_VALUES]
    + [f"I={v}" for v in CIA_VALUES]
    + [f"A={v}" for v in CIA_VALUES]
    + ["chain_depth", "in_degree", "out_degree"]
    + [f"cwe_h{i}" for i in range(CWE_HASH_DIM)]
)


@dataclass
class Dataset:
    X: np.ndarray            # (n_rows, n_features)
    y: np.ndarray            # (n_rows,) EPSS percentile in [0,1]
    groups: np.ndarray       # (n_rows,) original_cve — the split group
    images: np.ndarray       # (n_rows,) image name
    cve_ids: np.ndarray      # (n_rows,)
    feature_names: List[str]

    def __len__(self) -> int:
        return self.X.shape[0]


def build_dataset(corpus: dict, drop_structural: bool = False,
                  drop_vc: bool = False) -> Dataset:
    """Flatten the per-image DAG corpus into a labeled feature matrix.

    Uses the EPSS percentile as the target; drops node occurrences that have
    no percentile (CVE missing from the snapshot).

    ``drop_structural=True`` zeroes the graph-derived columns (chain_depth,
    in/out degree) → the pure node-intrinsic baseline (P0).
    ``drop_vc=True`` zeroes the Vector Changers (AV, PR, AC, UI) → measures
    how much the *non-VC* features (CWE, C/I/A impact) carry. Since the graph
    topology is a function of the VCs, this also bounds what message passing
    could add beyond VC-as-features.
    """
    comps = _component_maps(corpus)
    rows_X: List[List[float]] = []
    rows_y: List[float] = []
    groups: List[str] = []
    images: List[str] = []
    cve_ids: List[str] = []

    for g in corpus.get("graphs", []):
        indeg, outdeg = _degrees(g)
        for n in g.get("nodes", []):
            pct = n.get("epss_percentile")
            if pct is None:
                continue  # unlabeled → drop
            cve = n["cve_id"]
            c = comps.get((g["image"], cve), {})
            depth = n.get("chain_depth")
            vc = (lambda vals: [0.0] * len(vals)) if drop_vc else (lambda vals: None)
            feat = (
                (vc(AV_VALUES) or _onehot(n.get("av", ""), AV_VALUES))
                + (vc(PR_VALUES) or _onehot(n.get("pr", ""), PR_VALUES))
                + (vc(AC_VALUES) or _onehot(n.get("ac", ""), AC_VALUES))
                + (vc(UI_VALUES) or _onehot(n.get("ui", ""), UI_VALUES))
                + _onehot(c.get("C", ""), CIA_VALUES)
                + _onehot(c.get("I", ""), CIA_VALUES)
                + _onehot(c.get("A", ""), CIA_VALUES)
                + ([0.0, 0.0, 0.0] if drop_structural else [
                    float(depth) if depth is not None else -1.0,
                    float(indeg.get(cve, 0)),
                    float(outdeg.get(cve, 0)),
                ])
                + _cwe_hash(n.get("cwe_ids", []))
            )
            rows_X.append(feat)
            rows_y.append(float(pct))
            groups.append(cve)
            images.append(g["image"])
            cve_ids.append(cve)

    if not rows_X:
        return Dataset(
            X=np.empty((0, len(FEATURE_NAMES))), y=np.empty(0),
            groups=np.empty(0, dtype=object), images=np.empty(0, dtype=object),
            cve_ids=np.empty(0, dtype=object), feature_names=FEATURE_NAMES,
        )

    return Dataset(
        X=np.asarray(rows_X, dtype=np.float32),
        y=np.asarray(rows_y, dtype=np.float32),
        groups=np.asarray(groups, dtype=object),
        images=np.asarray(images, dtype=object),
        cve_ids=np.asarray(cve_ids, dtype=object),
        feature_names=FEATURE_NAMES,
    )


def _component_maps(corpus: dict) -> Dict[Tuple[str, str], Dict[str, str]]:
    """(image, cve) -> full CVSS component map (for C/I/A not stored as fields)."""
    out: Dict[Tuple[str, str], Dict[str, str]] = {}
    for g in corpus.get("graphs", []):
        for n in g.get("nodes", []):
            comps: Dict[str, str] = {}
            for part in (n.get("cvss_vector", "") or "").split("/"):
                if ":" in part:
                    k, v = part.split(":", 1)
                    comps[k] = v
            out[(g["image"], n["cve_id"])] = comps
    return out


def _degrees(graph: dict) -> Tuple[Dict[str, int], Dict[str, int]]:
    indeg: Dict[str, int] = defaultdict(int)
    outdeg: Dict[str, int] = defaultdict(int)
    for e in graph.get("edges", []):
        outdeg[e["source"]] += 1
        indeg[e["target"]] += 1
    return indeg, outdeg


def grouped_split(
    ds: Dataset,
    seed: int,
    val_frac: float = 0.15,
    test_frac: float = 0.15,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Split row indices into (train, val, test) grouped by ``original_cve``.

    A group (all occurrences of one CVE) is assigned wholly to one fold, so
    the same CVE never straddles folds (D22). Deterministic given ``seed``.
    Returns index arrays into the dataset rows.
    """
    rng = np.random.default_rng(seed)
    unique_groups = np.array(sorted(set(ds.groups.tolist())))
    rng.shuffle(unique_groups)

    n = len(unique_groups)
    n_test = int(round(n * test_frac))
    n_val = int(round(n * val_frac))
    test_g = set(unique_groups[:n_test].tolist())
    val_g = set(unique_groups[n_test:n_test + n_val].tolist())

    train_idx, val_idx, test_idx = [], [], []
    for i, gcve in enumerate(ds.groups.tolist()):
        if gcve in test_g:
            test_idx.append(i)
        elif gcve in val_g:
            val_idx.append(i)
        else:
            train_idx.append(i)

    return np.array(train_idx), np.array(val_idx), np.array(test_idx)


def assert_no_group_leak(ds: Dataset, train: np.ndarray, val: np.ndarray, test: np.ndarray) -> None:
    """Leakage sentinel (D22): the three folds share no ``original_cve``."""
    gt = set(ds.groups[train].tolist())
    gv = set(ds.groups[val].tolist())
    gs = set(ds.groups[test].tolist())
    assert not (gt & gv), "train/val share a CVE group"
    assert not (gt & gs), "train/test share a CVE group"
    assert not (gv & gs), "val/test share a CVE group"
