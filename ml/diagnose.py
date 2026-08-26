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
    graphs = corpus["graphs"]

    # Flatten node occurrences; aggregate degree per (image, cve) then reduce
    # to per-unique-CVE for the EPSS-signal questions (a CVE's label is global).
    per_cve_epss: Dict[str, float] = {}
    per_cve_okey: Dict[str, str] = {}
    per_cve_pkey: Dict[str, str] = {}
    per_cve_depths: Dict[str, List[int]] = defaultdict(list)
    per_cve_indeg: Dict[str, int] = defaultdict(int)
    per_cve_outdeg: Dict[str, int] = defaultdict(int)

    total_nodes = 0
    total_edges = 0
    for g in graphs:
        deg_in: Dict[str, int] = defaultdict(int)
        deg_out: Dict[str, int] = defaultdict(int)
        for e in g["edges"]:
            deg_out[e["source"]] += 1
            deg_in[e["target"]] += 1
            total_edges += 1
        for n in g["nodes"]:
            total_nodes += 1
            cid = n["cve_id"]
            per_cve_epss[cid] = n.get("epss_score") or 0.0
            per_cve_okey[cid] = n["outcome_key"]
            per_cve_pkey[cid] = n["prereq_key"]
            if n["chain_depth"] is not None:
                per_cve_depths[cid].append(n["chain_depth"])
            per_cve_indeg[cid] += deg_in.get(cid, 0)
            per_cve_outdeg[cid] += deg_out.get(cid, 0)

    ids = list(per_cve_epss.keys())
    print(f"=== {len(graphs)} image graphs | {total_nodes} node-occurrences | "
          f"{len(ids)} unique CVEs | {total_edges} edges ===\n")

    y = np.array([per_cve_epss[c] for c in ids])

    # --- 1. structure vs EPSS -------------------------------------------------
    indeg = np.array([per_cve_indeg[c] for c in ids], dtype=float)
    outdeg = np.array([per_cve_outdeg[c] for c in ids], dtype=float)
    # modal chain depth per CVE (0 if only ever depth 0; skip unreachable-only)
    depth_ids = [c for c in ids if per_cve_depths[c]]
    depth_vals = np.array([np.mean(per_cve_depths[c]) for c in depth_ids])
    depth_y = np.array([per_cve_epss[c] for c in depth_ids])
    print("[1] Structure vs EPSS (Spearman ρ):")
    print(f"    in-degree    ↔ EPSS : {spearman(indeg, y):+.3f}")
    print(f"    out-degree   ↔ EPSS : {spearman(outdeg, y):+.3f}")
    print(f"    chain-depth  ↔ EPSS : {spearman(depth_vals, depth_y):+.3f}   "
          f"(depth 1 = chain-dependent vs depth 0 = directly exploitable)")
    print("    (|ρ| near 0 ⇒ this structural feature carries little EPSS signal)\n")

    # --- 2. quotient class vs EPSS -------------------------------------------
    by_class: Dict[Tuple[str, str], List[float]] = defaultdict(list)
    for c in ids:
        by_class[(per_cve_pkey[c], per_cve_okey[c])].append(per_cve_epss[c])
    by_outcome: Dict[str, List[float]] = defaultdict(list)
    for c in ids:
        by_outcome[per_cve_okey[c]].append(per_cve_epss[c])
    by_depth: Dict[Any, List[float]] = defaultdict(list)
    for c in depth_ids:
        by_depth[round(float(np.mean(per_cve_depths[c])))].append(per_cve_epss[c])
    print("[2] Does membership explain EPSS? (η², 0..1):")
    print(f"    full (prereq,outcome) class : {eta_squared(by_class):.3f}")
    print(f"    outcome class only          : {eta_squared(by_outcome):.3f}")
    print(f"    chain depth                 : {eta_squared(by_depth):.3f}")
    print("    (low η² ⇒ EPSS varies mostly WITHIN these groups; the graph,")
    print("     being a function of them, then can't explain EPSS)\n")

    # --- 3. class coverage skew ----------------------------------------------
    sizes = sorted(Counter((per_cve_pkey[c], per_cve_okey[c]) for c in ids).values(), reverse=True)
    cum = np.cumsum(sizes) / len(ids)
    n_for_50 = int(np.searchsorted(cum, 0.50) + 1)
    n_for_90 = int(np.searchsorted(cum, 0.90) + 1)
    print("[3] Class coverage skew:")
    print(f"    {len(sizes)} classes total; "
          f"{n_for_50} class(es) cover 50% of unique CVEs, {n_for_90} cover 90%\n")

    # --- 4. per-image density -------------------------------------------------
    print("[4] Per-image graphs (nodes → edges):")
    for g in sorted(graphs, key=lambda g: -len(g["nodes"]))[:8]:
        nn, ne = len(g["nodes"]), len(g["edges"])
        dens = ne / (nn * (nn - 1)) if nn > 1 else 0.0
        print(f"    {g['image'][:34]:34s} {nn:4d} → {ne:6d}  (density {dens:.2f})")


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
