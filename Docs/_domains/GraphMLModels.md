# Graph-ML models (EPSS prediction)

Reference for the models built in `ml/` to predict a CVE's EPSS percentile from
the vulnerability-chain graph. This describes the **models** — architectures,
hyperparameters, parameter counts, and results. For the design rationale,
decision log, and the full experimental story see
[`Docs/Plans/GraphML_EPSS_Prediction.md`](../Plans/GraphML_EPSS_Prediction.md);
for how to run them see [`ml/README.md`](../../ml/README.md).

Status: experiment phase (GML-0/1/2 done). No model is served in production yet.

---

## Shared context (identical across all models)

All models solve the **same node-level regression** on the **same data**, so
that differences are attributable to the model, not the setup.

- **Task**: predict a CVE's **EPSS percentile** ∈ [0, 1] (the D15 target — a
  rank-uniform transform of raw EPSS, taken from the FIRST daily snapshot).
- **Loss** (neural models): MSE on the percentile. XGBoost uses its own
  squared-error objective on the same target.
- **Corpus**: a set of **per-image DAGs** (one graph per Docker image; nodes are
  CVEs, edges are directed "contribution" links from the attack-chain logic).
  Current corpus: 14 images, 886 unique CVEs, ~1254 labelled node occurrences.
- **Features** (55 columns, `ml/dataset.py::FEATURE_NAMES`):
  | Group | Features | Encoding | Cols |
  |---|---|---|---:|
  | State VCs (prereqs) | AV, PR | one-hot | 7 |
  | Environmental VCs (scenario) | AC, UI | one-hot | 4 |
  | CVSS impact | C, I, A | one-hot | 9 |
  | Graph-derived | chain_depth, in_degree, out_degree | scalar | 3 |
  | Weakness class | CWE | hashed multi-hot | 32 |

  Not used: CVE description text, CVE age, CPE/package embedding, KEV/Metasploit
  (all deferred). Ablation flags `--drop-vc` (zeros AV/PR/AC/UI) and
  `--drop-structural` (zeros chain_depth + degrees) carve out feature subsets.
- **Split**: three-way train/val/test, **grouped by `original_cve`** (D22), so a
  CVE that appears in several image graphs stays in one fold (no label leakage).
  A leakage sentinel asserts empty group intersection.
- **Metrics**: Spearman ρ (primary, ranking quality), top-decile precision
  (operational — the top of the list), MAE in percentile space. Reported as
  mean ± std over multiple seeds.

---

## The models

### 1. XGBoost — tabular baseline (out-of-family sanity check)
`ml/train.py::run_xgboost`, `ml/compare.py` config A.

- Gradient-boosted trees on the 55-column feature vector. No graph, no message
  passing — the reference the neural models are measured against.
- Hyperparameters: `n_estimators=400`, `max_depth=4`, `learning_rate=0.05`,
  `subsample=0.8`, `colsample_bytree=0.8`, `reg_lambda=1.0`,
  `tree_method="hist"`, early-stopping eval set = validation fold.
- "Parameters" (for the comparison figure): reported as tree count (~400) — a
  different unit from neural weights; see the figure's footnote.

### 2. 0-hop GNN / MLP — the neural anchor (no message passing)
Two closely-related implementations:

- **`ml/train.py::run_mlp`** (rung 2 of the main ladder): standardized inputs →
  `Linear(55→128) · ReLU · Dropout(0.2) · Linear(128→64) · ReLU · Dropout(0.2) ·
  Linear(64→1) · Sigmoid`. Adam (`lr=1e-3`, `weight_decay=1e-5`), MSE, 300
  epochs, best-validation checkpoint.
- **`ml/gnn.py::run_gnn(hops=0)`** (comparison config B/D): `Linear(55→128) ·
  ReLU · Dropout(0.2) · Linear(128→1) · Sigmoid` — a single hidden layer, so it
  is the exact 0-hop degenerate case of the GNN below (message passing switched
  off). ~7,297 parameters. This is the one plotted against the 1-hop GNN, so the
  0→1-hop comparison changes *only* whether edges are used.

Both are per-node MLPs — each CVE predicted from its own features alone.

### 3. 1-hop GNN — the graph model (one round of message passing)
`ml/gnn.py::run_gnn(hops=1)`, comparison config C.

- One `SAGEConv(55→128)` over the per-image DAG edges, then `ReLU · Dropout(0.2)
  · Linear(128→1) · Sigmoid`. ~14,337 parameters.
- Edges are the CVE→CVE contribution links, made **bidirectional** by default
  (a node aggregates both its enablers and what it enables); `--directed` keeps
  them one-way.
- Full-batch over all per-image graphs at once (no cross-image edges, so message
  passing stays within an image). Transductive node regression: the whole batch
  participates in message passing; loss/metrics only on the fold's nodes.
- Adam (`lr=1e-3`, `weight_decay=1e-5`), MSE, 400 epochs, best-validation
  checkpoint.

### 4. 2-hop GNN — deeper propagation
`ml/gnn.py::run_gnn(hops=2)`.

- Two stacked `SAGEConv` layers; otherwise identical to the 1-hop model.
- Included for completeness. On the current corpus (max chain depth 1) it
  **oversmooths** the dense per-image bicliques and underperforms 1-hop — useful
  hops ≈ max chain depth, so 1-hop is the right model here.

---

## The comparison configurations (A/B/C/D)

`ml/compare.py` runs four points that separate *architecture* from *how the
structure is supplied*. B and D share an architecture (0-hop) and parameter
count — they differ only in features.

| # | Model | Features | Structure reaches model via |
|---|---|---|---|
| A | XGBoost | minimal (CWE + impact) | — (no structure) |
| B | GNN 0-hop | minimal | — (no structure) |
| C | GNN 1-hop | minimal + edges | **message passing only** |
| D | GNN 0-hop | full (incl. VCs) | flattened into node features |

---

## Results (20-seed, grouped split, EPSS 2026-08-21)

| # | Model | Spearman ρ |
|---|---|---:|
| A | XGBoost (minimal) | 0.412 ± 0.076 |
| B | GNN 0-hop (minimal) | 0.340 ± 0.080 |
| **C** | **GNN 1-hop (edges only)** | **0.633 ± 0.096** |
| D | GNN 0-hop (full + VCs) | 0.703 ± 0.089 |

Full-feature 5-seed baselines (main ladder): XGBoost 0.742, 0-hop MLP 0.740,
1-hop GNN 0.740, 2-hop GNN 0.683.

**Reading the two ladders.** With the structure baked into features (full-feature
runs) the graph is redundant — 1-hop = 0-hop = ~0.74. With the structure hidden
from features and reaching the model **only through edges** (B→C), 1-hop message
passing lifts ρ +0.29 (0.34 → 0.63), recovering ~90 % of the full-VC model from
topology alone. So: the connections carry the exploitability signal, and the
Vector Changers (formally a graph feature) are the dominant predictor.

**Caveats.** Aggregate ρ ≈ 0.7 is strong for this task (EPSS uses inputs we lack,
so the achievable ceiling is well below 1), but **top-decile precision is only
~0.4–0.55** — the operationally important top of the ranking is more modest. One
container-scan corpus, shallow chains (depth ≤ 1), imbalanced (`python:latest`
dominates).

---

## Where to look

- Data / features / split: `ml/dataset.py`, `ml/labels.py`
- Metrics: `ml/metrics.py`
- Training: `ml/train.py` (rungs 1–2), `ml/gnn.py` (rungs 3–4)
- Comparison figure: `ml/compare.py` → `ml/out/compare_runs/<ts>/`
- Chain graph construction: `src/core/chain.py`, `ml/exporter.py`
- Full plan & decision log: `Docs/Plans/GraphML_EPSS_Prediction.md`
