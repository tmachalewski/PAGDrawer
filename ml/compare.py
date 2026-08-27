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


def _draw_violin(ax, x, vals, color):
    """Manual violin on a log-x axis: KDE evaluated over y, drawn as a filled
    polygon whose half-width is symmetric in log space (so it isn't skewed by
    xscale='log'). Falls back to a thin bar if KDE is degenerate."""
    import numpy as np
    try:
        from scipy.stats import gaussian_kde
        kde = gaussian_kde(vals)
        pad = 0.05 * (vals.max() - vals.min() + 1e-6)
        ygrid = np.linspace(vals.min() - pad, vals.max() + pad, 200)
        dens = kde(ygrid)
        hw = 0.13 * dens / dens.max()          # max half-width in log units
        ax.fill_betweenx(ygrid, x * np.exp(-hw), x * np.exp(hw),
                         color=color, alpha=0.30, lw=0, zorder=2)
        ax.plot(x * np.exp(hw), ygrid, color=color, lw=0.8, alpha=0.6, zorder=2)
        ax.plot(x * np.exp(-hw), ygrid, color=color, lw=0.8, alpha=0.6, zorder=2)
    except Exception:
        ax.plot([x, x], [vals.min(), vals.max()], color=color, lw=8, alpha=0.3, zorder=2)


def render(bundle: Dict, out: str, style: str = "candle") -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    results = bundle["results"]
    colors = {"minimal": "#3b7dd8", "full": "#d8663b"}

    fig, ax = plt.subplots(figsize=(8.5, 5.4))

    # Models that share a parameter count (same architecture) sit at the SAME
    # x — their vertical separation keeps them from overlapping. For each such
    # group, the top model gets its name above, the others below, so labels
    # don't collide. `label_above` marks the upper model of a shared group.
    from collections import defaultdict
    groups = defaultdict(list)
    for i, r in enumerate(results):
        groups[r["n_params"]].append(i)
    label_above, label_below = set(), set()
    shared = []
    for p, idxs in groups.items():
        if len(idxs) > 1:
            shared.append([results[i]["key"] for i in idxs])
            order = sorted(idxs, key=lambda j: np.nanmedian(results[j]["spearman"]))
            label_below.add(order[0])   # lower model: labels go below
            label_above.add(order[-1])  # upper model: labels go above

    for i, r in enumerate(results):
        x = max(r["n_params"], 1)
        vals = np.array([v for v in r["spearman"] if not np.isnan(v)])
        c = colors[r["feature_set"]]
        lo, hi = vals.min(), vals.max()
        q1, med, q3 = np.percentile(vals, [25, 50, 75])
        if style == "violin":
            _draw_violin(ax, x, vals, c)
            ax.plot([x * 0.90, x * 1.10], [med, med], color=c, lw=2.4, zorder=4)
            dot_x = x * 0.87
        else:  # candlestick
            ax.plot([x, x], [lo, hi], color=c, lw=1.2, zorder=2)
            ax.plot([x, x], [q1, q3], color=c, lw=9, alpha=0.28, zorder=2, solid_capstyle="butt")
            ax.plot([x * 0.90, x * 1.10], [med, med], color=c, lw=2.4, zorder=4)
            dot_x = x * 0.93
        # seed dots sit at a fixed x (all seeds of a model have identical
        # params); spread is purely vertical (per-seed Spearman).
        ax.scatter(np.full(len(vals), dot_x), vals, s=18, color=c, alpha=0.55,
                   edgecolor="white", lw=0.3, zorder=5)
        # Labels. For a shared-x pair the lower model keeps everything below
        # its candle and the upper model everything above, so the two don't
        # collide. Non-shared models: key above, name below (default).
        if i in label_below:
            ax.annotate(r["key"], (x, lo), textcoords="offset points", xytext=(0, -12),
                        ha="center", va="top", fontsize=12, fontweight="bold", color=c, zorder=6)
            ax.annotate(r["label"], (x, lo), textcoords="offset points", xytext=(0, -28),
                        ha="center", va="top", fontsize=8, color="#333", zorder=6)
        elif i in label_above:
            ax.annotate(r["key"], (x, hi), textcoords="offset points", xytext=(0, 24),
                        ha="center", fontsize=12, fontweight="bold", color=c, zorder=6)
            ax.annotate(r["label"], (x, hi), textcoords="offset points", xytext=(0, 8),
                        ha="center", fontsize=8, color="#333", zorder=6)
        else:
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


def render_both(bundle: Dict, out_dir: str) -> None:
    """Render both the candlestick and the violin figure into out_dir."""
    render(bundle, os.path.join(out_dir, "model_comparison"), style="candle")
    render(bundle, os.path.join(out_dir, "model_comparison_violin"), style="violin")


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
        render_both(bundle, os.path.dirname(src))
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

    render_both(bundle, run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
