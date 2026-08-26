"""GML-2 — graph rungs (3 = 1-hop, 4 = 2-hop) on the per-image DAG corpus.

Tests the plan's core question at last: does explicit message passing over the
chain graph add anything beyond the (already graph-derived) node features?

Design:
  * one PyG graph per Docker image (no cross-image edges), batched together —
    message passing stays inside each image.
  * the SAME feature matrix and the SAME D22 grouped-by-original_cve split as
    the tabular baselines, so rung 2 (0-hop) → rung 3/4 isolates message
    passing as the only change.
  * transductive node regression: the whole batch participates in message
    passing; loss/metrics only on the fold's nodes; val/test labels never
    enter the loss.
  * edges are the directed contribution edges; by default made bidirectional
    so a node sees both its enablers and what it enables (gives the GNN the
    best chance — a null under bidirectional is a robust null).

Full-batch on GPU (corpus is small; the biclique cap the plan mentions is only
needed at larger scale).

Usage:
    python -m ml.gnn ml/out/corpus_v2.json --label-date 2026-08-21 \
        --hops 1 --seeds 5
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


def build_pyg_batch(ds: Dataset, corpus: dict, bidirectional: bool = True):
    """Build one batched PyG graph: per-image subgraphs, no cross-image edges.

    Each node keeps its global dataset row index in ``ridx`` so split masks
    (defined over dataset rows) map onto batch nodes.
    """
    import torch
    from torch_geometric.data import Data, Batch

    # dataset rows are emitted image-by-image in build_dataset order; recover
    # per-image row ranges by matching (image, cve_id).
    row_lookup: Dict[tuple, int] = {}
    for i in range(len(ds)):
        row_lookup[(ds.images[i], ds.cve_ids[i])] = i

    data_list = []
    for g in corpus.get("graphs", []):
        img = g["image"]
        local_rows = [row_lookup.get((img, n["cve_id"])) for n in g["nodes"]]
        # keep only labeled nodes (those that made it into ds)
        keep = [(n["cve_id"], r) for n, r in zip(g["nodes"], local_rows) if r is not None]
        if not keep:
            continue
        cve_to_local = {cve: k for k, (cve, _) in enumerate(keep)}
        ridx = [r for _, r in keep]

        src, dst = [], []
        for e in g.get("edges", []):
            a, b = cve_to_local.get(e["source"]), cve_to_local.get(e["target"])
            if a is None or b is None:
                continue
            src.append(a); dst.append(b)
            if bidirectional:
                src.append(b); dst.append(a)

        x = torch.tensor(ds.X[ridx], dtype=torch.float32)
        y = torch.tensor(ds.y[ridx], dtype=torch.float32).unsqueeze(1)
        edge_index = (torch.tensor([src, dst], dtype=torch.long)
                      if src else torch.empty((2, 0), dtype=torch.long))
        d = Data(x=x, edge_index=edge_index, y=y)
        d.ridx = torch.tensor(ridx, dtype=torch.long)
        data_list.append(d)

    return Batch.from_data_list(data_list)


def _mask(ridx, idx_set, device):
    import torch
    keep = np.isin(ridx.cpu().numpy(), idx_set)
    return torch.tensor(keep, dtype=torch.bool, device=device)


def run_gnn(ds: Dataset, batch, tr, va, te, seed: int, hops: int,
            writer=None, epochs: int = 400) -> Dict[str, float]:
    import torch
    import torch.nn as nn
    from torch_geometric.nn import SAGEConv

    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # standardize on train rows
    mu = ds.X[tr].mean(axis=0, keepdims=True)
    sd = ds.X[tr].std(axis=0, keepdims=True) + 1e-6
    b = batch.clone().to(device)
    b.x = ((b.x - torch.tensor(mu, device=device)) / torch.tensor(sd, device=device)).float()

    tr_mask = _mask(b.ridx, set(tr.tolist()), device)
    va_mask = _mask(b.ridx, set(va.tolist()), device)
    te_mask = _mask(b.ridx, set(te.tolist()), device)

    class Net(nn.Module):
        def __init__(self, in_dim, hidden=128, hops=1):
            super().__init__()
            self.hops = hops
            if hops == 0:
                self.lin1 = nn.Linear(in_dim, hidden)
            else:
                self.convs = nn.ModuleList(
                    [SAGEConv(in_dim if i == 0 else hidden, hidden) for i in range(hops)]
                )
            self.drop = nn.Dropout(0.2)
            self.head = nn.Linear(hidden, 1)

        def forward(self, x, edge_index):
            if self.hops == 0:
                h = torch.relu(self.lin1(x))
            else:
                h = x
                for conv in self.convs:
                    h = torch.relu(conv(h, edge_index))
            h = self.drop(h)
            return torch.sigmoid(self.head(h))

    model = Net(ds.X.shape[1], hops=hops).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
    loss_fn = nn.MSELoss()

    best_val, best_state = float("inf"), None
    for ep in range(epochs):
        model.train()
        opt.zero_grad()
        out = model(b.x, b.edge_index)
        loss = loss_fn(out[tr_mask], b.y[tr_mask])
        loss.backward()
        opt.step()

        model.eval()
        with torch.no_grad():
            out = model(b.x, b.edge_index)
            vloss = loss_fn(out[va_mask], b.y[va_mask]).item()
        if writer is not None:
            writer.add_scalar(f"hops{hops}/seed{seed}/train_loss", loss.item(), ep)
            writer.add_scalar(f"hops{hops}/seed{seed}/val_loss", vloss, ep)
        if vloss < best_val:
            best_val = vloss
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        out = model(b.x, b.edge_index)
        tpred = out[te_mask].cpu().numpy().ravel()
    ytrue = b.y[te_mask].cpu().numpy().ravel()
    return evaluate(ytrue, tpred)


def _agg(results: List[Dict[str, float]]) -> Dict[str, str]:
    out = {}
    for k in results[0].keys():
        vals = np.array([r[k] for r in results], dtype=float)
        out[k] = f"{np.nanmean(vals):+.3f} ± {np.nanstd(vals):.3f}"
    return out


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="GML-2 graph rungs (1-/2-hop GNN).")
    ap.add_argument("corpus")
    ap.add_argument("--label-date", required=True)
    ap.add_argument("--snapshot", default=None)
    ap.add_argument("--hops", type=int, default=1, choices=[0, 1, 2])
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--epochs", type=int, default=400)
    ap.add_argument("--directed", action="store_true", help="use directed edges (default: bidirectional)")
    ap.add_argument("--no-tensorboard", action="store_true")
    args = ap.parse_args(argv)

    with open(args.corpus, "r", encoding="utf-8") as fh:
        corpus = json.load(fh)

    snap_path = args.snapshot or f"ml/out/epss_scores-{args.label_date}.csv.gz"
    if not os.path.exists(snap_path):
        print(f"Downloading EPSS snapshot {args.label_date}...", file=sys.stderr)
        download_snapshot(args.label_date, snap_path)
    snapshot = load_snapshot(snap_path)
    report = attach_labels(corpus, snapshot)
    print(f"EPSS {snapshot.score_date} ({snapshot.model_version}); "
          f"coverage {report.coverage:.1%}", file=sys.stderr)

    ds = build_dataset(corpus)
    batch = build_pyg_batch(ds, corpus, bidirectional=not args.directed)
    print(f"Dataset {len(ds)} rows × {ds.X.shape[1]} feats; "
          f"batch {batch.num_nodes} nodes, {batch.num_edges} edges "
          f"({'directed' if args.directed else 'bidirectional'}); hops={args.hops}\n",
          file=sys.stderr)

    writer = None
    if not args.no_tensorboard:
        from torch.utils.tensorboard import SummaryWriter
        writer = SummaryWriter(log_dir=f"ml/runs/gml2_h{args.hops}_{args.label_date}")

    res: List[Dict[str, float]] = []
    for seed in range(args.seeds):
        tr, va, te = grouped_split(ds, seed=seed)
        assert_no_group_leak(ds, tr, va, te)
        res.append(run_gnn(ds, batch, tr, va, te, seed, args.hops, writer, args.epochs))
        print(f"  seed {seed}: ρ={res[-1]['spearman']:+.3f}", file=sys.stderr)

    print(f"\n=== GML-2 rung {2 + args.hops} — {args.hops}-hop GNN "
          f"(mean ± std over {args.seeds} seeds) ===")
    print(f"  {_agg(res)}")
    if writer is not None:
        writer.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
