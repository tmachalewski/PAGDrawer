"""GML-1 — non-graph baselines (rungs 1 and 2).

Rung 1: XGBoost on the tabular features (out-of-family sanity check).
Rung 2: 0-hop GNN = an MLP per node (the neural-family anchor; message
        passing disabled). torch, on GPU when available.

Both use the identical feature matrix and the D22 grouped split, so the
rung-1→rung-2 comparison is apples-to-apples. Reported over multiple seeds as
mean±std (seed variance at ~900 CVEs can exceed rung deltas). TensorBoard
logs go to ``ml/runs/``.

Usage:
    python -m ml.train ml/out/corpus_v2.json --label-date 2026-08-21 --seeds 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List

import numpy as np

from ml.dataset import build_dataset, grouped_split, assert_no_group_leak, Dataset
from ml.labels import load_snapshot, download_snapshot, attach_labels
from ml.metrics import evaluate

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# --------------------------------------------------------------------------- #
# Rung 1 — XGBoost
# --------------------------------------------------------------------------- #

def run_xgboost(ds: Dataset, tr, va, te, seed: int) -> Dict[str, float]:
    from xgboost import XGBRegressor

    model = XGBRegressor(
        n_estimators=400,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        random_state=seed,
        n_jobs=0,
        tree_method="hist",
    )
    model.fit(
        ds.X[tr], ds.y[tr],
        eval_set=[(ds.X[va], ds.y[va])],
        verbose=False,
    )
    pred = model.predict(ds.X[te])
    return evaluate(ds.y[te], pred)


# --------------------------------------------------------------------------- #
# Rung 2 — 0-hop GNN (MLP per node)
# --------------------------------------------------------------------------- #

def run_mlp(ds: Dataset, tr, va, te, seed: int, writer=None, epochs: int = 300) -> Dict[str, float]:
    import torch
    import torch.nn as nn

    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # standardize features on train stats
    mu = ds.X[tr].mean(axis=0, keepdims=True)
    sd = ds.X[tr].std(axis=0, keepdims=True) + 1e-6
    Xz = (ds.X - mu) / sd

    Xt = torch.tensor(Xz, dtype=torch.float32, device=device)
    yt = torch.tensor(ds.y, dtype=torch.float32, device=device).unsqueeze(1)
    tr_t = torch.tensor(tr, dtype=torch.long, device=device)
    va_t = torch.tensor(va, dtype=torch.long, device=device)
    te_t = torch.tensor(te, dtype=torch.long, device=device)

    model = nn.Sequential(
        nn.Linear(ds.X.shape[1], 128), nn.ReLU(), nn.Dropout(0.2),
        nn.Linear(128, 64), nn.ReLU(), nn.Dropout(0.2),
        nn.Linear(64, 1), nn.Sigmoid(),          # target is a percentile in [0,1]
    ).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
    loss_fn = nn.MSELoss()

    best_val = float("inf")
    best_state = None
    for ep in range(epochs):
        model.train()
        opt.zero_grad()
        pred = model(Xt[tr_t])
        loss = loss_fn(pred, yt[tr_t])
        loss.backward()
        opt.step()

        model.eval()
        with torch.no_grad():
            vpred = model(Xt[va_t])
            vloss = loss_fn(vpred, yt[va_t]).item()
        if writer is not None:
            writer.add_scalar(f"seed{seed}/train_loss", loss.item(), ep)
            writer.add_scalar(f"seed{seed}/val_loss", vloss, ep)
        if vloss < best_val:
            best_val = vloss
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        tpred = model(Xt[te_t]).cpu().numpy().ravel()
    return evaluate(ds.y[te], tpred)


# --------------------------------------------------------------------------- #
# Harness
# --------------------------------------------------------------------------- #

def _agg(results: List[Dict[str, float]]) -> Dict[str, str]:
    keys = results[0].keys()
    out = {}
    for k in keys:
        vals = np.array([r[k] for r in results], dtype=float)
        out[k] = f"{np.nanmean(vals):+.3f} ± {np.nanstd(vals):.3f}"
    return out


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="GML-1 non-graph baselines (rungs 1-2).")
    ap.add_argument("corpus", help="corpus JSON from ml.export_corpus")
    ap.add_argument("--label-date", required=True, help="EPSS snapshot date YYYY-MM-DD")
    ap.add_argument("--snapshot", default=None, help="path to a cached epss_scores-*.csv.gz")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--epochs", type=int, default=300)
    ap.add_argument("--no-tensorboard", action="store_true")
    ap.add_argument("--drop-structural", action="store_true",
                    help="P0 ablation: zero chain_depth + degree features (pure node-intrinsic)")
    ap.add_argument("--drop-vc", action="store_true",
                    help="VC ablation: zero the Vector Changers (AV/PR/AC/UI)")
    args = ap.parse_args(argv)

    with open(args.corpus, "r", encoding="utf-8") as fh:
        corpus = json.load(fh)

    snap_path = args.snapshot or f"ml/out/epss_scores-{args.label_date}.csv.gz"
    if not os.path.exists(snap_path):
        print(f"Downloading EPSS snapshot {args.label_date}...", file=sys.stderr)
        download_snapshot(args.label_date, snap_path)
    snapshot = load_snapshot(snap_path)
    report = attach_labels(corpus, snapshot)
    print(f"EPSS snapshot {snapshot.score_date} ({snapshot.model_version}), "
          f"{len(snapshot)} scores", file=sys.stderr)
    print(f"Label coverage: {report.labeled_cves}/{report.unique_cves} unique CVEs "
          f"({report.coverage:.1%}); {report.labeled_nodes}/{report.total_nodes} node rows",
          file=sys.stderr)

    ds = build_dataset(corpus, drop_structural=args.drop_structural, drop_vc=args.drop_vc)
    parts = []
    parts.append("no depth/degree" if args.drop_structural else "with structural")
    parts.append("no VCs" if args.drop_vc else "with VCs")
    print(f"Dataset: {len(ds)} labeled rows × {ds.X.shape[1]} features  [{', '.join(parts)}]\n",
          file=sys.stderr)

    writer = None
    if not args.no_tensorboard:
        from torch.utils.tensorboard import SummaryWriter
        writer = SummaryWriter(log_dir=f"ml/runs/gml1_{args.label_date}")

    xgb_res: List[Dict[str, float]] = []
    mlp_res: List[Dict[str, float]] = []
    for seed in range(args.seeds):
        tr, va, te = grouped_split(ds, seed=seed)
        assert_no_group_leak(ds, tr, va, te)   # D22 leakage sentinel
        xgb_res.append(run_xgboost(ds, tr, va, te, seed))
        mlp_res.append(run_mlp(ds, tr, va, te, seed, writer=writer, epochs=args.epochs))
        print(f"  seed {seed}: xgb ρ={xgb_res[-1]['spearman']:+.3f}  "
              f"mlp ρ={mlp_res[-1]['spearman']:+.3f}", file=sys.stderr)

    print("\n=== GML-1 baselines (mean ± std over "
          f"{args.seeds} seeds, grouped split by original_cve) ===")
    print(f"Rung 1  XGBoost      : {_agg(xgb_res)}")
    print(f"Rung 2  0-hop (MLP)  : {_agg(mlp_res)}")

    if writer is not None:
        writer.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
