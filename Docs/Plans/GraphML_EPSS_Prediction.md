# Graph ML: EPSS Prediction over the Vulnerability-Chain Graph

Status: **planned** (post-GD-2026 work). Decisions below were settled in a design discussion on 2026-08-22; this document is the staged implementation plan.

---

## 1. Research question

> **Does a CVE's position in the network of feasible attack chains carry exploitability signal beyond its own attributes?**

In plain terms: do real-world attackers (as observed by EPSS) prefer vulnerabilities that are well-*connected* — easily reached by chains and unlocking much once exploited? Nobody else can ask this question the way PAGDrawer can, because the chaining relation ("outcomes of *a* satisfy prerequisites of *b*") is the project's own VC-framework contribution.

Secondary, practical payoffs:

- **EPSS imputation** for fresh/unscored CVEs.
- **Residual visualization** in PAGDrawer: color CVE nodes by `predicted − actual` EPSS. Nodes the structure "believes" should be hotter or colder than FIRST says are exactly what an analyst should inspect. This ties the ML module back to the tool's core identity — visualization.

## 2. Decision log

These were discussed and settled; do not re-litigate without new evidence.

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Per-date model** (predict EPSS as of a stamped model date), not time-series | PoC simplicity; retrain often. EPSS label MUST carry the FIRST model date. (Amended by D9: labels come from one daily CSV snapshot; the drift study is future work.) |
| D2 | **CVE-centric graph**, not heterogeneous schema graph | In the hetero graph, VC info is 3 hops from CVE (CVE→CWE→TI→VC); a GNN would need ≥3 layers just to see its own outcomes, and deep GNNs oversmooth on small graphs. Chain attributes are folded into CVE node features instead. |
| D3 | **Drop HOST entirely; deduplicate to one node per `original_cve`** | EPSS is a global property of the CVE — identical for every copy across hosts/CPEs. Host context is noise w.r.t. this label. Dedup kills the duplicate-leakage problem at the root (no more group-split machinery needed). Environment-dependent features (`chain_depth`, `layer`, host counts) are dropped with it. |
| D4 | **CWE and CPE as node features only**, not edge relations | `shared_CWE` creates near-cliques (CWE-79 alone links thousands of CVEs pairwise → O(n²) edges, oversmoothing, giant components). The class signal lives in the feature; the ablation ladder (§6) will test whether relation variants add anything. |
| D5 | **Edges = directed `enables` relation from VC matching** | `a → b` iff `outcomes(a) ⊨ prereqs(b)` (consensual matrix). Computable globally from CVE data alone — survives dedup, host-independent like the label, directed (in-neighborhood = "my stepping stones", out-neighborhood = "what I unlock"), and is the semantic core of the project. |
| D6 | **The ML graph is a separate artifact from the visualization graph** | Built from the deduplicated CVE corpus, not from a scan's rendered graph. PAGDrawer re-enters at the end as the lens: residuals overlaid on a concrete environment's attack graph. |
| D7 | **Baseline ladder is mandatory** (§6) | The whole thesis is "structure adds signal beyond local features"; without tabular baselines the GNN result is uninterpretable. |
| D8 | **0-hop GNN is the primary structural baseline** (2026-08-24) | Same architecture / features / optimizer with message passing disabled (an MLP per node). Isolates exactly one variable — edge propagation — which the XGBoost comparison cannot (different model family, capacity, regularization). XGBoost stays as an out-of-family sanity check. |
| D9 | **Labels from FIRST daily CSV snapshots, same-date prediction** (2026-08-24) | `epss_scores-YYYY-MM-DD.csv.gz` — one atomic file = one consistent model date for the whole corpus (API calls spread over time can straddle a model update), no rate limits, archivable next to the model artifact for full reproducibility. Task is pure same-date imputation; the D+30 drift study is demoted to future work. |
| D10 | **Three-way split (train/val/test)** (2026-08-24) | Hyperparameters are tuned — so tuning looks only at validation; test is evaluated once per model family. k-fold CV on train+val for HP selection at this corpus size; multiple seeds, report mean±std (seed variance can exceed rung deltas at ~1–2k nodes). |

## 3. Graph specification

**Nodes** — unique CVEs (deduplicated by `original_cve`).

**Node features:**

| Feature | Encoding | Source |
|---|---|---|
| CVSS vector components (AV, AC, PR, UI, C, I, A) | one-hot per component | NVD cache |
| CWE id(s) | learned `nn.Embedding` (multi-hot pooled if several) | NVD cache |
| CPE / package | hash-embedding of product | Trivy / NVD |
| Age (days since publication), days since last NVD modification | scalar, log-scaled | NVD cache |
| Prereq vector + `vc_outcomes` multi-hot (Vector Changers) | multi-hot; same information as the CVE-merge keys, unserialized | VC framework |
| CVE description text (optional, ablation flag) | sentence-transformer embedding (e.g. MiniLM 384d), computed offline in the exporter and cached in Mongo; PCA-reduce to ~32–64 dims at small corpus sizes | NVD cache (`description` field, already fetched) |

Not included (dropped with D3): `chain_depth`, `layer`, per-host/per-scan context. Never included: EPSS itself (label).

**VC features play a dual role** — they are node features *and* the predicate that generates `enables` edges. Intentional, but it shapes interpretation: if the multi-hop GNN fails to beat the 0-hop baseline, one candidate explanation is "the VC features already encode what the edges would deliver", since topology is a function of these features.

**Text-feature caveat**: EPSS's own model consumes text-derived tags, so description embeddings partially overlap the label's inputs. Fine for imputation quality — but text may absorb structural signal, which is why ±text is a separate ablation rung, not part of the base feature set.

**Edges** — directed `enables`: `a → b` iff outcomes(a) satisfy prereqs(b) per the consensual matrix (see `Docs/ConsensualMatrix_TrascribedByHand.md`, chain logic in `src/graph/builder.py`).

Known structural property (accept and handle, don't fight):
- The relation is a function of (outcome-key, prereq-key) pairs, whose vocabulary is small — the same equivalence classes as the M22/ACR merge keys. The graph is therefore a *blow-up of a small quotient graph* over key classes: all CVEs with the same key pair have identical structural neighborhoods. What the GNN adds over features is **corpus-level statistics of neighbor classes** (which CWEs/packages/labels actually populate "the class that enables me"), which a per-node model cannot see. This is precisely what the ablation ladder measures.
- Compatible classes form large bicliques → cap or sample neighbors per class (GraphSAGE-style neighbor sampling; cap is a tuned hyperparameter).

Optional second relation for ablation only: `shared_CPE` (CVEs sharing a vulnerable product, built from NVD CPE configurations — global, like the label — not from scans).

## 4. Task & labels

- **Task**: node-level regression. Target: `logit(EPSS)` (raw EPSS is extremely right-skewed: median ~0.001, tail to 0.99). Loss: MSE in logit space.
- **Metrics**: Spearman ρ (primary — ranking is what practitioners consume), MAE in probability space (secondary).
- **Labels** (per D9): one FIRST **daily CSV snapshot** — `epss_scores-YYYY-MM-DD.csv.gz` (published daily since 2021). One atomic file gives every CVE in the corpus a label from the same model date; the file is archived next to the model artifact for reproducibility. The per-CVE API (`nvd_fetcher.py:34`) remains the source for the *visualization* path; the ML pipeline uses the bulk file. Prediction target is the **same date** as the label snapshot — pure imputation, no forecasting.

## 5. Architecture

Follows the existing `Scripts/start-*.sh` + docker-compose pattern:

```
docker-compose:  mongo  +  backend (FastAPI)  +  ml (NEW container)
```

- **`ml/` service** — separate FastAPI app with its own image (torch + PyTorch Geometric are heavy; keep them out of the backend image). Endpoints:
  - `POST /train` — accepts a corpus export, trains, stores artifact.
  - `POST /predict` — returns per-CVE predicted EPSS (+ residual if actual is known).
  - `GET /model/info` — version, EPSS model date, eval metrics, corpus hash.
- **Backend** — gains `GET /api/ml/export` (deduplicated CVE corpus + enables edges as JSON/tensors) and a thin proxy `GET /api/ml/predictions` so the frontend keeps a single origin.
- **Model artifacts** — MongoDB GridFS, next to the NVD/EPSS caches. Each artifact records: git SHA, corpus snapshot hash, EPSS model date, hyperparameters, eval metrics. Same provenance discipline as the metrics JSON export.
- **Model** — 2 layers of directed message passing (separate in/out aggregation — direction is semantic here), SAGE-style neighbor sampling. Inductive by construction.
- **Scripts** — `Scripts/start-ml.sh` / `Scripts/kill-ml.sh`, same conventions as the rest.

## 6. Evaluation protocol

**Split** (per D10): **three-way** — train / validation / test over deduplicated CVE nodes. Hyperparameter tuning reads only validation; test is evaluated **once**, at the end, per model family. At this corpus size, prefer k-fold CV on (train+val) for HP selection, then a final fit and a single test evaluation. Run ≥3 seeds and report mean±std — seed variance at ~1–2k nodes can exceed the deltas between ladder rungs. Keep one **leakage sentinel**: `assert len(train_cves & test_cves) == 0` on `original_cve` sets — one line, catches future regressions if dedup is ever accidentally dropped.

**Transductive masking**: the full graph participates in message passing; loss and metrics are computed only on the respective split's nodes. Validation/test labels never enter the loss.

**The baseline ladder** (per D8; each rung isolates one claim):

| Rung | Model | What beating the previous rung proves |
|---|---|---|
| 1 | XGBoost on own features (CVSS + CWE + CPE + age) | out-of-family sanity check; roughly reproduces "EPSS from static features" |
| 2 | **GNN 0-hop** — same architecture/features/training, message passing disabled (MLP per node) | anchor of the neural family; everything above is measured against this |
| 3 | GNN 1-hop on the enables graph | one round of neighbor aggregation adds signal — *position in the chain network matters* |
| 4 | GNN 2-hop | deeper propagation still pays (watch oversmoothing) |
| A1 (ablation) | rung 3/4 ± description-text embedding | text feature contribution; also reveals whether text absorbs structural signal |
| A2 (ablation) | rung 3/4 + `shared_CPE` second relation | product co-location adds anything on top of `enables` |
| A3 (cheap side-check) | rung 1 + enables-graph centralities (in/out-degree, PageRank) as tabular features | two numbers of structure in a tabular model — if this already helps, the signal is robust |

The structural contribution is the delta **rung 2 → rung 3/4**, measured within one model family. If it is not meaningful (Spearman margin > seed std), that negative result is itself informative — one candidate explanation is the VC dual role (§3): topology is a function of the VC features, so the features may already carry what the edges would deliver.

**Additional evaluation regime**:
- **Label-density stratification**: report test metrics bucketed by fraction of train-labeled neighbors (0% / <50% / ≥50%). Measures how much the transductive setting inflates results vs. the cold-start production case.

## 7. Data / corpus

Because the graph and label are both global (D3, D5), the corpus is **not limited by Trivy scans**. Options in order of scale:

1. **Scan-derived corpus** (start here): union of unique CVEs across the 9-image examples corpus (+ any new scans). Small (~1–2k unique CVEs) but the pipeline exists end-to-end today.
2. **Extended scan corpus**: Trivy-scan ~100–200 popular Docker Hub images (automatable; ingest pipeline exists). ~5–15k unique CVEs, same distribution as production use.
3. **Full NVD corpus**: all CVEs with CVSS v3 vectors (~200k). Only needed if rung-3 results look promising and data-hungry; requires bulk NVD ingest rather than per-CVE fetch.

## 8. Stages

Modeled on the metrics-roadmap staging. Each stage lands independently with tests.

- **Stage GML-0 — Corpus exporter.** Backend: dedup by `original_cve`, assemble features, compute enables edges from VC matching, emit versioned JSON. Unit tests on a synthetic mini-corpus (known keys → known edges). *Acceptance: export is deterministic (stable hash) for a fixed cache state.*
- **Stage GML-1 — Labels + non-graph baselines.** Download + archive one FIRST daily CSV snapshot (D9); label join with model-date stamp; three-way split with leakage sentinel (D10); rung 1 (XGBoost) and rung 2 (0-hop GNN); metrics report (Spearman/MAE, mean±std over seeds). *Acceptance: rungs 1–2 documented with seed variance; split protocol frozen.*
- **Stage GML-2 — ML service scaffold.** `ml/` container, docker-compose entry, Scripts, `/train` + `/predict` + `/model/info`, GridFS artifacts (with the label-snapshot file hash). Rung-1/2 models served (multi-hop GNN not needed to ship the service). *Acceptance: end-to-end train→persist→predict cycle through the API.*
- **Stage GML-3 — Multi-hop GNN.** PyG directed SAGE (1- and 2-hop rungs, neighbor sampling with biclique cap), ablations A1–A3. Label-density stratification report. *Acceptance: ladder table complete; go/no-go call on graph ML recorded here.*
- **Stage GML-4 — Residual overlay in PAGDrawer.** Frontend: color CVE nodes by residual (diverging palette), tooltip shows predicted vs actual vs model date. Works with whatever the best available rung is. *Acceptance: overlay toggling documented in StatisticsModal/DebugOverlay docs.*

Decision gate after GML-3: if multi-hop rungs don't pay, GML-4 still ships on rung 2 (or rung 1 + centralities from A3).

**Future work (out of mainline)**: drift study — per-date model matrix (train on snapshot D, evaluate on snapshot D+Δ) using FIRST's historical daily files; yields a retraining-cadence recommendation. One paragraph here on purpose; revisit only after the imputation results are in.

## 9. Risks & open questions

- **Biclique density of `enables`** — neighbor cap is a band-aid; if the quotient structure dominates, consider modeling class-level aggregates directly as features (cheap alternative to GNN). Measure first (GML-0 emits degree histograms).
- **Corpus size at stage 1** (~1–2k CVEs) is small for embeddings (CWE/CPE) — freeze embedding dims small (8–16) or defer hash-embeddings to corpus option 2.
- **CVEs without CVSS v3 vectors** have no prereq/outcome keys → isolated nodes. Report their share; they still work in tabular rungs.
- **Open**: exact satisfaction semantics of `outcomes(a) ⊨ prereqs(b)` for edge construction — reuse the backend chain-building predicate from `src/graph/builder.py` verbatim (single source of truth), do not re-derive in the exporter.

## 10. Cross-references

- VC framework & consensual matrix: `Docs/VC_Framework_Paper.md`, `Docs/ConsensualMatrix_TrascribedByHand.md`
- Chain construction: `Docs/Plans/Chain_Depth_Aware_Attack_Stages.md`, `src/graph/builder.py`
- Merge keys (same equivalence classes as the enables quotient): `frontend/js/features/mergeKeys.ts`, `Docs/_domains/PaperAlgorithms.md` §3
- EPSS fetching & caching: `src/data/loaders/nvd_fetcher.py`, `Docs/_domains/MongoDBPersistence.md`
- Staging pattern this plan imitates: `Docs/Plans/Master_Implementation_Roadmap.md`
