"""GML-0.5 — deep diagnostics on an exported corpus.

Answers the questions that decide how much GNN effort is warranted, BEFORE
any model is written (per the 2026-08-26 decision to run full diagnostics
first):

  1. Does the enables graph carry EPSS signal at all? — Spearman of
     in/out-degree and PageRank against EPSS.
  2. Does the quotient class predict EPSS? — between-class vs within-class
     EPSS variance (eta^2). If class explains little, the graph (which is a
     function of the classes) cannot explain much either.
  3. How skewed is class coverage? — cumulative node share by class.
  4. How many edges are escalating vs lateral/redundant? — informs whether a
     narrower `enables` definition (escalation-only) is worth pursuing.

Pure numpy + networkx; no scipy. Run:
    venv/Scripts/python.exe -m ml.diagnose ml/out/corpus_full.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
import networkx as nx

# Windows consoles default to cp1252 and choke on ρ/η/↔. Force UTF-8 so the
# report renders identically everywhere.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover - non-reconfigurable stream
    pass


def _avg_ranks(x: np.ndarray) -> np.ndarray:
    """Ranks with ties averaged (for Spearman)."""
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), dtype=float)
    ranks[order] = np.arange(len(x), dtype=float)
    # average tied groups
    _, inv, counts = np.unique(x, return_inverse=True, return_counts=True)
    csum = np.cumsum(counts)
    starts = csum - counts
    avg = (starts + csum - 1) / 2.0
    return avg[inv]


def spearman(a: Sequence[float], b: Sequence[float]) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if len(a) < 3 or np.all(a == a[0]) or np.all(b == b[0]):
        return float("nan")
    ra, rb = _avg_ranks(a), _avg_ranks(b)
    ra -= ra.mean(); rb -= rb.mean()
    denom = np.sqrt((ra * ra).sum() * (rb * rb).sum())
    return float((ra * rb).sum() / denom) if denom else float("nan")


def eta_squared(groups: Dict[Any, List[float]]) -> float:
    """Fraction of EPSS variance explained by group membership (0..1)."""
    allv = np.array([v for g in groups.values() for v in g], dtype=float)
    if len(allv) < 2:
        return float("nan")
    grand = allv.mean()
    ss_total = ((allv - grand) ** 2).sum()
    if ss_total == 0:
        return float("nan")
    ss_between = sum(len(g) * (np.mean(g) - grand) ** 2 for g in groups.values() if g)
    return float(ss_between / ss_total)


def _pagerank_numpy(G: "nx.DiGraph", ids: Sequence[str], alpha: float = 0.85,
                    iters: int = 100, tol: float = 1e-9) -> np.ndarray:
    """Power-iteration PageRank in numpy (nx 3.x routes pagerank through scipy,
    which we don't depend on). Dangling nodes redistribute uniformly."""
    n = len(ids)
    if n == 0:
        return np.zeros(0)
    idx = {c: i for i, c in enumerate(ids)}
    out = np.array([G.out_degree(c) for c in ids], dtype=float)
    r = np.full(n, 1.0 / n)
    # adjacency as list of (src_i, tgt_i)
    src = np.array([idx[e[0]] for e in G.edges()], dtype=int)
    tgt = np.array([idx[e[1]] for e in G.edges()], dtype=int)
    for _ in range(iters):
        contrib = np.zeros(n)
        # each edge passes r[src]/out[src] to tgt
        np.add.at(contrib, tgt, r[src] / out[src])
        dangling = r[out == 0].sum()
        new = (1 - alpha) / n + alpha * (contrib + dangling / n)
        if np.abs(new - r).sum() < tol:
            r = new
            break
        r = new
    return r


def analyze(corpus: Dict[str, Any]) -> None:
    nodes = corpus["nodes"]
    edges = corpus["edges"]
    ids = [n["cve_id"] for n in nodes]
    epss = {n["cve_id"]: (n.get("epss_score") or 0.0) for n in nodes}
    okey = {n["cve_id"]: n["outcome_key"] for n in nodes}
    pkey = {n["cve_id"]: n["prereq_key"] for n in nodes}

    G = nx.DiGraph()
    G.add_nodes_from(ids)
    G.add_edges_from((e["source"], e["target"]) for e in edges)

    print(f"=== {len(ids)} nodes, {G.number_of_edges()} edges "
          f"(density {nx.density(G):.3f}) ===\n")

    # --- 1. structure vs EPSS -------------------------------------------------
    y = np.array([epss[c] for c in ids])
    indeg = np.array([G.in_degree(c) for c in ids], dtype=float)
    outdeg = np.array([G.out_degree(c) for c in ids], dtype=float)
    print("[1] Structure vs EPSS (Spearman ρ):")
    print(f"    in-degree   ↔ EPSS : {spearman(indeg, y):+.3f}")
    print(f"    out-degree  ↔ EPSS : {spearman(outdeg, y):+.3f}")
    prv = _pagerank_numpy(G, ids)
    print(f"    PageRank    ↔ EPSS : {spearman(prv, y):+.3f}")
    print("    (|ρ| near 0 ⇒ this structural feature carries little EPSS signal)\n")

    # --- 2. quotient class vs EPSS -------------------------------------------
    by_class: Dict[Tuple[str, str], List[float]] = defaultdict(list)
    for c in ids:
        by_class[(pkey[c], okey[c])].append(epss[c])
    e2_full = eta_squared(by_class)
    by_outcome: Dict[str, List[float]] = defaultdict(list)
    for c in ids:
        by_outcome[okey[c]].append(epss[c])
    e2_out = eta_squared(by_outcome)
    print("[2] Does class membership explain EPSS? (η², 0..1):")
    print(f"    full (prereq,outcome) class : {e2_full:.3f}")
    print(f"    outcome class only          : {e2_out:.3f}")
    print("    (low η² ⇒ EPSS varies mostly WITHIN classes; the enables graph,")
    print("     being a function of these classes, then can't explain EPSS)\n")

    # --- 3. class coverage skew ----------------------------------------------
    sizes = sorted(Counter((pkey[c], okey[c]) for c in ids).values(), reverse=True)
    cum = np.cumsum(sizes) / len(ids)
    n_for_50 = int(np.searchsorted(cum, 0.50) + 1)
    n_for_90 = int(np.searchsorted(cum, 0.90) + 1)
    print("[3] Class coverage skew:")
    print(f"    {len(sizes)} classes total; "
          f"{n_for_50} class(es) cover 50% of nodes, {n_for_90} cover 90%\n")

    # --- 4. escalating vs lateral edges --------------------------------------
    lateral = sum(1 for e in edges if okey[e["source"]] == okey[e["target"]])
    total = len(edges)
    print("[4] Edge character:")
    print(f"    lateral/redundant (same outcome class) : {lateral}/{total} "
          f"({lateral/total:.1%})" if total else "    (no edges)")
    print(f"    potentially escalating                 : {total - lateral}/{total} "
          f"({(total-lateral)/total:.1%})" if total else "")
    print("    (high lateral share ⇒ a narrower escalation-only `enables`")
    print("     would prune many edges without losing capability lift)")


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Deep diagnostics on an ML corpus export.")
    ap.add_argument("corpus", help="path to corpus.json from ml.export_corpus")
    args = ap.parse_args(argv)
    with open(args.corpus, "r", encoding="utf-8") as fh:
        corpus = json.load(fh)
    analyze(corpus)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
