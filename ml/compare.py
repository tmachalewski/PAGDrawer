"""GML — model comparison figure (params vs quality, seed spread).

Runs the four models that tell the story (see the plan §6, Ladders A/B) over
many seeds, records per-seed test Spearman + parameter counts to a JSON, and
renders a single presentation figure:

    x = number of model parameters (log)
    y = Spearman ρ (EPSS-percentile ranking quality)
    per model: a candlestick (range / IQR / median) + the individual seed dots

Models (A/B/C/D):
  A  XGBoost           minimal features (CWE + impact; no VCs, no depth/degree)
  B  GNN 0-hop         minimal features
  C  GNN 1-hop         minimal features + edges   (structure only via connections)
  D  GNN 0-hop         full features (with VCs)    (structure flattened into features)

B vs C isolates message passing (same features); A/B vs D isolates the VC
features. Results are cached so the chart re-renders without retraining:
    python -m ml.compare ml/out/corpus_v2.json --label-date 2026-08-21 --seeds 20
    python -m ml.compare ml/out/corpus_v2.json --label-date 2026-08-21 --render-only
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List

import numpy as np

from ml.dataset import build_dataset, grouped_split, assert_no_group_leak
from ml.labels import load_snapshot, download_snapshot, attach_labels
from ml.metrics import evaluate

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

RUNS_DIR = "ml/out/compare_runs"          # each run archived in its own subfolder
LATEST_LINK = "ml/out/compare_latest.json"  # convenience pointer to the newest run

# (key, label, model, hops, drop_vc, drop_structural, feature_set)
CONFIGS = [
    ("A", "XGBoost\n(minimal feats)", "xgb", 0, True, True, "minimal"),
    ("B", "GNN 0-hop\n(minimal feats)", "gnn", 0, True, True, "minimal"),
    ("C", "GNN 1-hop\n(edges only)", "gnn", 1, True, True, "minimal"),
    ("D", "GNN 0-hop\n(full feats + VC)", "gnn", 0, False, False, "full"),
]


def _xgb_param_count(model) -> int:
    """Proxy 'parameters' for XGBoost: total nodes across all trees."""
    try:
        df = model.get_booster().trees_to_dataframe()
        return int(len(df))
    except Exception:
        return int(getattr(model, "n_estimators", 0))


def _run_config(cfg, corpus, label_date, seeds, epochs) -> Dict:
    import torch
    key, label, kind, hops, dvc, dstruct, feats = cfg
    ds = build_dataset(corpus, drop_structural=dstruct, drop_vc=dvc)

    spearmans: List[float] = []
    top_dec: List[float] = []
    n_params = 0

    if kind == "xgb":
        from xgboost import XGBRegressor
        for seed in range(seeds):
            tr, va, te = grouped_split(ds, seed=seed)
            assert_no_group_leak(ds, tr, va, te)
            m = XGBRegressor(n_estimators=400, max_depth=4, learning_rate=0.05,
                             subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0,
                             random_state=seed, n_jobs=0, tree_method="hist")
            m.fit(ds.X[tr], ds.y[tr], eval_set=[(ds.X[va], ds.y[va])], verbose=False)
            r = evaluate(ds.y[te], m.predict(ds.X[te]))
            spearmans.append(r["spearman"]); top_dec.append(r["top_decile_precision"])
            n_params = _xgb_param_count(m)
    else:
        from ml.gnn import build_pyg_batch, run_gnn
        batch = build_pyg_batch(ds, corpus, bidirectional=True)
        for seed in range(seeds):
            tr, va, te = grouped_split(ds, seed=seed)
            assert_no_group_leak(ds, tr, va, te)
            r = run_gnn(ds, batch, tr, va, te, seed=seed, hops=hops, writer=None, epochs=epochs)
            spearmans.append(r["spearman"]); top_dec.append(r["top_decile_precision"])
        # param count: rebuild the same Net once and count
        n_params = _gnn_param_count(ds.X.shape[1], hops)

    return {
        "key": key, "label": label, "kind": kind, "hops": hops,
        "feature_set": feats, "n_params": n_params,
        "spearman": spearmans, "top_decile": top_dec,
        "spearman_mean": float(np.nanmean(spearmans)),
        "spearman_std": float(np.nanstd(spearmans)),
    }


def _gnn_param_count(in_dim, hops) -> int:
    import torch
    from ml.gnn import run_gnn  # noqa: F401  (ensures torch/PyG import path)
    import torch.nn as nn
    from torch_geometric.nn import SAGEConv
    if hops == 0:
        mods = [nn.Linear(in_dim, 128), nn.Linear(128, 1)]
    else:
        mods = [SAGEConv(in_dim if i == 0 else 128, 128) for i in range(hops)] + [nn.Linear(128, 1)]
    return int(sum(p.numel() for m in mods for p in m.parameters()))


def run_all(corpus, label_date, seeds, epochs) -> Dict:
    results = []
    for cfg in CONFIGS:
        print(f"  [{cfg[0]}] {cfg[1].splitlines()[0]} — {seeds} seeds...", file=sys.stderr)
        res = _run_config(cfg, corpus, label_date, seeds, epochs)
        print(f"       ρ = {res['spearman_mean']:+.3f} ± {res['spearman_std']:.3f}  "
              f"({res['n_params']} params)", file=sys.stderr)
        results.append(res)
    return {"label_date": label_date, "seeds": seeds, "epochs": epochs, "results": results}


def render(bundle: Dict, out: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    results = bundle["results"]
    colors = {"minimal": "#3b7dd8", "full": "#d8663b"}

    fig, ax = plt.subplots(figsize=(8.5, 5.4))

    # spread configs that share a parameter count (same architecture) so their
    # candlesticks don't overlap; note it as an honest annotation.
    from collections import defaultdict
    groups = defaultdict(list)
    for i, r in enumerate(results):
        groups[r["n_params"]].append(i)
    xpos = {}
    shared = []
    for p, idxs in groups.items():
        if len(idxs) == 1:
            xpos[idxs[0]] = p
        else:
            factors = np.linspace(0.90, 1.10, len(idxs))
            for f, i in zip(factors, idxs):
                xpos[i] = p * f
            shared.append([results[i]["key"] for i in idxs])

    for i, r in enumerate(results):
        x = max(xpos[i], 1)
        vals = np.array([v for v in r["spearman"] if not np.isnan(v)])
        c = colors[r["feature_set"]]
        lo, hi = vals.min(), vals.max()
        q1, med, q3 = np.percentile(vals, [25, 50, 75])
        ax.plot([x, x], [lo, hi], color=c, lw=1.2, zorder=2)
        ax.plot([x, x], [q1, q3], color=c, lw=9, alpha=0.28, zorder=2, solid_capstyle="butt")
        ax.plot([x * 0.90, x * 1.10], [med, med], color=c, lw=2.4, zorder=4)
        # seed dots sit at the EXACT parameter count (no horizontal jitter —
        # all seeds of a model have identical params). Overplotting shows as
        # density via alpha; a hair of x-offset only to lift dots off the line.
        ax.scatter(np.full(len(vals), x * 0.93), vals, s=18, color=c, alpha=0.55,
                   edgecolor="white", lw=0.3, zorder=5)
        # key letter above the candle; model name below it
        ax.annotate(r["key"], (x, hi), textcoords="offset points", xytext=(0, 10),
                    ha="center", fontsize=12, fontweight="bold", color=c, zorder=6)
        ax.annotate(r["label"], (x, lo), textcoords="offset points", xytext=(0, -30),
                    ha="center", fontsize=8, color="#333", zorder=6)
        ax.annotate(f"ρ̄={r['spearman_mean']:.2f}", (x * 1.11, med), textcoords="offset points",
                    xytext=(3, 0), ha="left", va="center", fontsize=7.5, color=c, zorder=6)

    ax.set_xscale("log")
    ax.set_xlabel("model parameters (log scale;  XGBoost = tree-node count)")
    ax.set_ylabel("Spearman ρ  (EPSS-percentile ranking)")
    ax.set_title(f"EPSS prediction: how the model accesses vulnerability structure\n"
                 f"({bundle['seeds']} seeds, grouped split by original_cve, "
                 f"EPSS {bundle['label_date']})", fontsize=11)
    ax.grid(True, which="both", axis="y", alpha=0.25)
    ax.grid(True, which="major", axis="x", alpha=0.15)
    ax.margins(x=0.15, y=0.18)

    from matplotlib.lines import Line2D
    legend = [
        Line2D([0], [0], color=colors["minimal"], lw=6, alpha=0.5,
               label="minimal features (structure via edges only)"),
        Line2D([0], [0], color=colors["full"], lw=6, alpha=0.5,
               label="full features (VCs flattened in)"),
    ]
    ax.legend(handles=legend, loc="upper left", fontsize=8, framealpha=0.9)

    if shared:
        note = "; ".join("=".join(g) + " share a parameter count (same architecture)" for g in shared)
        ax.annotate(note, (0.5, -0.16), xycoords="axes fraction", ha="center",
                    fontsize=7.5, color="#666", style="italic")

    fig.tight_layout()
    for ext in ("svg", "png"):
        path = f"{out}.{ext}"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        print(f"Wrote {path}", file=sys.stderr)
    plt.close(fig)


def _latest_run() -> str:
    """Path to the results.json of the most recent archived run."""
    if not os.path.isdir(RUNS_DIR):
        raise FileNotFoundError(f"No runs in {RUNS_DIR}")
    runs = sorted(d for d in os.listdir(RUNS_DIR) if os.path.isdir(os.path.join(RUNS_DIR, d)))
    if not runs:
        raise FileNotFoundError(f"No runs in {RUNS_DIR}")
    return os.path.join(RUNS_DIR, runs[-1], "results.json")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Model comparison figure (params vs Spearman).")
    ap.add_argument("corpus", nargs="?")
    ap.add_argument("--label-date", default=None)
    ap.add_argument("--snapshot", default=None)
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--epochs", type=int, default=400)
    ap.add_argument("--tag", default=None, help="optional label appended to the run-folder name")
    ap.add_argument("--render-only", action="store_true",
                    help="re-render a cached run instead of training")
    ap.add_argument("--from", dest="from_run", default=None,
                    help="results.json (or run folder) to render; default: latest run")
    args = ap.parse_args(argv)

    if args.render_only:
        src = args.from_run or _latest_run()
        if os.path.isdir(src):
            src = os.path.join(src, "results.json")
        with open(src, "r", encoding="utf-8") as fh:
            bundle = json.load(fh)
        render(bundle, os.path.join(os.path.dirname(src), "model_comparison"))
        return 0

    if not args.corpus or not args.label_date:
        ap.error("corpus and --label-date are required for a training run")

    with open(args.corpus, "r", encoding="utf-8") as fh:
        corpus = json.load(fh)
    snap_path = args.snapshot or f"ml/out/epss_scores-{args.label_date}.csv.gz"
    if not os.path.exists(snap_path):
        download_snapshot(args.label_date, snap_path)
    attach_labels(corpus, load_snapshot(snap_path))

    bundle = run_all(corpus, args.label_date, args.seeds, args.epochs)

    # archive this run in its own timestamped folder — never overwrite prior runs
    from datetime import datetime
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}_{args.seeds}seeds"
    if args.tag:
        stamp += f"_{args.tag}"
    run_dir = os.path.join(RUNS_DIR, stamp)
    os.makedirs(run_dir, exist_ok=True)
    bundle["run_dir"] = run_dir
    results_path = os.path.join(run_dir, "results.json")
    with open(results_path, "w", encoding="utf-8") as fh:
        json.dump(bundle, fh, indent=2)
    # convenience pointer to the newest run
    with open(LATEST_LINK, "w", encoding="utf-8") as fh:
        json.dump({"latest": results_path}, fh, indent=2)
    print(f"Archived run: {run_dir}", file=sys.stderr)

    render(bundle, os.path.join(run_dir, "model_comparison"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
