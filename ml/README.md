# Graph-ML: EPSS prediction

Predicts EPSS (exploit-probability percentile) for CVEs from the
vulnerability-chain graph. Implements the plan in
[`Docs/Plans/GraphML_EPSS_Prediction.md`](../Docs/Plans/GraphML_EPSS_Prediction.md)
(decision log D1–D22 + results). Experiment phase — plain scripts, GPU, no
service container (per D16).

## Headline result (2026-08-27)

The research question (§1 of the plan) — *does vulnerability-chain information
improve EPSS prediction?* — is answered **yes**, but only when the graph is
tested fairly. Full 20-seed ladder (grouped split by `original_cve`):

| Model | features | Spearman ρ |
|---|---|---:|
| A — XGBoost | minimal (CWE + impact) | 0.412 ± 0.076 |
| B — GNN 0-hop | minimal | 0.340 ± 0.080 |
| **C — GNN 1-hop** | **minimal + edges** | **0.633 ± 0.096** |
| D — GNN 0-hop | full (with VCs) | 0.703 ± 0.089 |

- **B → C = +0.29**: with structure hidden from features, 1-hop message passing
  over the chain edges recovers ~90 % of the full VC-feature model **from
  topology alone** → *the connections carry the exploitability signal*.
- **A/B → D = +0.28**: the Vector Changers are the dominant EPSS predictor
  (CWE+impact 0.46 → +VCs 0.70).
- VCs are *formally a graph feature* (schema nodes flattened into node features
  per D2), so both readings agree: the exploitability signal lives in the
  chain structure.
- **Hops ≈ max chain depth.** This corpus maxes at depth 1, so 1-hop spans the
  whole chain; 2-hop oversmooths the dense bicliques (ρ drops to ~0.46). Don't
  read the earlier "message passing doesn't pay" note — that was a *confounded*
  ladder (structure given as features AND edges); see plan §6 Ladders A/B.

## Layout

| File | Stage | Role |
|------|-------|------|
| `../src/core/chain.py` | shared | Single-source chain primitives: `escalating_outcomes`, `assign_chain_depths`, `contributes`. Builder + exporter both use these (predicate `prereqs_satisfied` in `consensual_matrix.py`). |
| `exporter.py` | GML-0 | Pure corpus builder: **per-image DAGs**, depth-layered chains, contribution edges, diagnostics. No Mongo/network. |
| `export_corpus.py` | GML-0 | CLI: load Trivy scans → enrich → write `corpus.json` (set of image graphs). Needs Mongo caches. |
| `diagnose.py` | GML-0.5 | Structure↔EPSS analysis (Spearman of degree/depth, η² of classes, per-image density). |
| `labels.py` | GML-1 | Download/parse a FIRST daily EPSS snapshot; join the percentile target by CVE; provenance stamp. |
| `dataset.py` | GML-1 | Feature matrix (CVSS one-hot incl. categorical AC/UI, chain_depth, degree, hashed CWE) + grouped split by `original_cve` (D22). `--drop-vc`/`--drop-structural` ablations. |
| `metrics.py` | GML-1 | Spearman + top-decile precision + MAE (pure numpy). |
| `train.py` | GML-1 | Rung 1 (XGBoost) + rung 2 (0-hop MLP, GPU), multi-seed, TensorBoard. |
| `gnn.py` | GML-2 | Rungs 3/4 (1-/2-hop SAGEConv) on per-image PyG graphs; same grouped split; `--drop-vc`/`--drop-structural`. |
| `compare.py` | figure | Runs models A/B/C/D over N seeds → archives each run in `out/compare_runs/<ts>/` (results.json + candlestick + violin). |

## The graph (per-image DAGs)

One directed acyclic graph **per Docker image** (chains link only CVEs on the
same image — reality-pruning). Built by `core.chain`: attacker baseline
`{(AV,N),(PR,N)}` → admit CVEs whose AV/PR prereqs are met → accumulate their
**escalating** outcomes → advance depth (monotonic ⇒ DAG). CVE→CVE
**contribution** edges: `a → b` iff `depth(a) < depth(b)` and a's escalating
outcomes supply a VC b's prereqs need (layer-skipping allowed). The same CVE
appears in several image graphs → the split groups by `original_cve` (D22).

**Vector Changers**: state VCs (AV, PR, EX) build topology; environmental VCs
(AC, UI) are the fixed input scenario — categorical node features, not state
(D21). Scenario is fixed **maximal** (AC:H, UI:R → nothing pruned).

## Environment (GPU)

torch is installed from the **CUDA 12.8** index (Blackwell / RTX 50xx = sm_120
needs cu128; Python 3.14 wheels exist as of torch 2.11):

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install scikit-learn xgboost torch-geometric tensorboard matplotlib
```

Note: XGBoost's DLL is blocked by an Application Control policy inside the
Claude Code agent sandbox (WinError 4551) — XGBoost runs must be launched from
a normal user terminal. torch/PyG work in both.

## Reproduce

```bash
bash Scripts/start-mongo.sh                    # caches for enrichment

# GML-0: build the per-image DAG corpus (--ignore-ttl reuses an aged cache)
python -m ml.export_corpus "examples/*.json" --ignore-ttl \
    --label-date 2026-08-21 -o ml/out/corpus_v2.json
python -m ml.diagnose ml/out/corpus_v2.json    # structure↔EPSS signal

# GML-1: labels + tabular/0-hop baselines (downloads the EPSS snapshot)
python -m ml.train ml/out/corpus_v2.json --label-date 2026-08-21 --seeds 20
#   ablations: --drop-vc  --drop-structural

# GML-2: graph rungs (structure only via edges = the fair test)
python -m ml.gnn ml/out/corpus_v2.json --label-date 2026-08-21 \
    --hops 1 --drop-vc --drop-structural --seeds 20

# Comparison figure A/B/C/D (both candlestick + violin, archived per run)
python -m ml.compare ml/out/corpus_v2.json --label-date 2026-08-21 \
    --seeds 20 --tag baseline
python -m ml.compare --render-only            # re-render latest without training
```

EPSS labels come from one FIRST daily snapshot
(`https://epss.empiricalsecurity.com/epss_scores-YYYY-MM-DD.csv.gz`) — it
carries the `percentile` column (the D15 target) and a model-date header.

## Tests

```bash
PAGDRAWER_SKIP_MONGO=1 venv/Scripts/python.exe -m pytest \
    tests/test_chain.py tests/test_ml_exporter.py tests/test_ml_gml1.py -q
```

## Next (not done)

- **A4 ablation**: does 1-hop beat class-aggregate features (is the signal
  topological or just class-statistical)?
- **Grow the corpus** (§7 option 2: 100+ images) → deeper chains where
  multi-hop could matter.
- **GML-3/4**: serving container + residual overlay in PAGDrawer (colour CVE
  nodes by predicted−actual EPSS) — can ship on the tabular or the GNN model.
