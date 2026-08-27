# Project status — Graph-ML EPSS prediction thread (2026-08-27)

Post-publication (GD 2026 done). This note captures the Graph-ML thread so it
survives context compression. Full detail:
[`Docs/Plans/GraphML_EPSS_Prediction.md`](../Plans/GraphML_EPSS_Prediction.md)
and [`ml/README.md`](../../ml/README.md).

## What we built

A GPU pipeline that predicts a CVE's EPSS percentile from the
vulnerability-chain graph, as a **set of per-image DAGs** (one graph per Docker
image; chains link only co-occurring CVEs). Code in `ml/`, shared chain
primitives in `src/core/chain.py`, plan in `Docs/Plans/`.

Stages done: **GML-0** (corpus exporter + diagnostics), **GML-1** (EPSS labels
from FIRST daily snapshot + XGBoost/0-hop baselines), **GML-2** (1-/2-hop GNN),
plus a comparison figure (`ml/compare.py`). Not done: A4 ablation, corpus
growth, GML-3/4 (service + residual overlay).

## The result (the important part)

Research question: *does vulnerability-chain information improve EPSS
prediction?* → **yes, on this corpus**, when tested fairly. 20-seed ladder,
grouped split by `original_cve`:

| Model | features | Spearman ρ |
|---|---|---:|
| A XGBoost | minimal (CWE+impact) | 0.412 ± 0.076 |
| B GNN 0-hop | minimal | 0.340 ± 0.080 |
| **C GNN 1-hop** | **minimal + edges** | **0.633 ± 0.096** |
| D GNN 0-hop | full (+VCs) | 0.703 ± 0.089 |

- **B→C +0.29**: hide the structure from features and 1-hop message passing
  recovers ~90 % of the full-VC model **from topology alone** → the connections
  carry the exploitability signal.
- **VCs are the dominant predictor** (+0.28) and are *formally a graph feature*
  → both readings agree: signal lives in the chain structure.
- **Two publishable framings**: (a) the VC framework predicts EPSS; (b) the
  chain graph carries it, recoverable by a GNN from edges alone.

## Traps we hit (so we don't repeat them)

1. **First exporter was a global pairwise closure**, not per-image — cross-image
   fictional edges + cycles (not a DAG). Fixed to per-image DAGs reusing the
   builder's depth logic. (D19/D20)
2. **First GNN ladder was confounded**: structure given as node features AND
   edges → graph looked useless (1-hop = 0-hop = 0.74). The fair test hides
   structure from features (`--drop-vc --drop-structural`) so edges are the only
   channel → then 1-hop clearly wins. This reversed the verdict.
3. **Hops must ≈ max chain depth.** Corpus depth is 1 → 1-hop is right; 2-hop
   oversmooths the bicliques (ρ→0.46).
4. **Split leakage**: same CVE in many image graphs → group by `original_cve`.
5. **np.isin(x, set)** silently returns all-False (0-d object array) → empty
   masks, nan metrics. Pass arrays, not sets.

## Environment

- GPU: RTX 5090 Laptop (Blackwell sm_120), torch 2.11.0+cu128, Python 3.14.
- Install torch from `https://download.pytorch.org/whl/cu128`; sklearn, xgboost,
  torch-geometric, tensorboard, matplotlib pinned in `requirements.txt`.
- XGBoost DLL is blocked in the Claude Code agent sandbox (WinError 4551) →
  XGBoost runs from the user's terminal; torch/PyG run anywhere.

## Data / artifacts

- Corpus: `ml/out/corpus_v2.json` (14 images, 886 unique CVEs, all DAGs).
- EPSS labels: FIRST daily snapshot `epss_scores-2026-08-21.csv.gz` (has the
  `percentile` column = the D15 target).
- Figures: `ml/out/compare_runs/<ts>/` — candlestick + violin, per run.
  (`ml/out/` is gitignored; regenerate from the corpus + snapshot.)

## Next steps (when resumed)

1. **A4 ablation** — 1-hop vs class-aggregate features (topological vs
   class-statistical signal).
2. **Grow corpus** to 100+ images → deeper chains, real test for multi-hop.
3. **GML-4 residual overlay** in PAGDrawer (colour CVE nodes by predicted−actual
   EPSS) — the visualization payoff; works on the tabular or GNN model.
