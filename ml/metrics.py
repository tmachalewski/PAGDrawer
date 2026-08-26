"""GML-1 — evaluation metrics (D15).

Co-primary: Spearman ρ and top-decile precision. Secondary: MAE.
Pure numpy so the metric code has no heavy deps and is trivially testable.
"""

from __future__ import annotations

from typing import Dict

import numpy as np


def _avg_ranks(x: np.ndarray) -> np.ndarray:
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), dtype=float)
    ranks[order] = np.arange(len(x), dtype=float)
    _, inv, counts = np.unique(x, return_inverse=True, return_counts=True)
    csum = np.cumsum(counts)
    starts = csum - counts
    avg = (starts + csum - 1) / 2.0
    return avg[inv]


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if len(a) < 3 or np.all(a == a[0]) or np.all(b == b[0]):
        return float("nan")
    ra, rb = _avg_ranks(a), _avg_ranks(b)
    ra -= ra.mean(); rb -= rb.mean()
    denom = np.sqrt((ra * ra).sum() * (rb * rb).sum())
    return float((ra * rb).sum() / denom) if denom else float("nan")


def top_decile_precision(y_true: np.ndarray, y_pred: np.ndarray, q: float = 0.9) -> float:
    """Share of the true top-(1-q) fraction recovered in the predicted top
    fraction of equal size. Ranking quality at the top, which is what
    practitioners consume (D15)."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    n = len(y_true)
    if n == 0:
        return float("nan")
    k = max(1, int(round(n * (1.0 - q))))
    true_top = set(np.argsort(-y_true)[:k].tolist())
    pred_top = set(np.argsort(-y_pred)[:k].tolist())
    return len(true_top & pred_top) / k


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(np.asarray(y_true, float) - np.asarray(y_pred, float))))


def evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    return {
        "spearman": spearman(y_true, y_pred),
        "top_decile_precision": top_decile_precision(y_true, y_pred),
        "mae": mae(y_true, y_pred),
    }
