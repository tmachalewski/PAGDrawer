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
| D1 | **Per-date model** (predict EPSS as of a stamped model date), not time-series | PoC simplicity; retrain often; many per-date models enable cheap drift/stability analysis (train on day D, test on labels from D+30). EPSS label MUST carry the FIRST model date. |
| D2 | **CVE-centric graph**, not heterogeneous schema graph | In the hetero graph, VC info is 3 hops from CVE (CVE→CWE→TI→VC); a GNN would need ≥3 layers just to see its own outcomes, and deep GNNs oversmooth on small graphs. Chain attributes are folded into CVE node features instead. |
| D3 | **Drop HOST entirely; deduplicate to one node per `original_cve`** | EPSS is a global property of the CVE — identical for every copy across hosts/CPEs. Host context is noise w.r.t. this label. Dedup kills the duplicate-leakage problem at the root (no more group-split machinery needed). Environment-dependent features (`chain_depth`, `layer`, host counts) are dropped with it. |
| D4 | **CWE and CPE as node features only**, not edge relations | `shared_CWE` creates near-cliques (CWE-79 alone links thousands of CVEs pairwise → O(n²) edges, oversmoothing, giant components). The class signal lives in the feature; the ablation ladder (§6) will test whether relation variants add anything. |
| D5 | **Edges = directed `enables` relation from VC matching** | `a → b` iff `outcomes(a) ⊨ prereqs(b)` (consensual matrix). Computable globally from CVE data alone — survives dedup, host-independent like the label, directed (in-neighborhood = "my stepping stones", out-neighborhood = "what I unlock"), and is the semantic core of the project. |
| D6 | **The ML graph is a separate artifact from the visualization graph** | Built from the deduplicated CVE corpus, not from a scan's rendered graph. PAGDrawer re-enters at the end as the lens: residuals overlaid on a concrete environment's attack graph. |
| D7 | **Baseline ladder is mandatory** (§6) | The whole thesis is "structure adds signal beyond local features"; without tabular baselines the GNN result is uninterpretable. |

## 3. Graph specification

**Nodes** — unique CVEs (deduplicated by `original_cve`).

**Node features:**

| Feature | Encoding | Source |
|---|---|---|
| CVSS vector components (AV, AC, PR, UI, C, I, A) | one-hot per component | NVD cache |
| CWE id(s) | learned `nn.Embedding` (multi-hot pooled if several) | NVD cache |
| CPE / package | hash-embedding of product | Trivy / NVD |
| Age (days since publication), days since last NVD modification | scalar, log-scaled | NVD cache |
| Prereq key, outcome key | already computed — same keys as CVE merge (`mergeKeys.ts` contract; backend equivalent) | VC framework |

Not included (dropped with D3): `chain_depth`, `layer`, per-host/per-scan context. Never included: EPSS itself (label).

**Edges** — directed `enables`: `a → b` iff outcomes(a) satisfy prereqs(b) per the consensual matrix (see `Docs/ConsensualMatrix_TrascribedByHand.md`, chain logic in `src/graph/builder.py`).

Known structural property (accept and handle, don't fight):
- The relation is a function of (outcome-key, prereq-key) pairs, whose vocabulary is small — the same equivalence classes as the M22/ACR merge keys. The graph is therefore a *blow-up of a small quotient graph* over key classes: all CVEs with the same key pair have identical structural neighborhoods. What the GNN adds over features is **corpus-level statistics of neighbor classes** (which CWEs/packages/labels actually populate "the class that enables me"), which a per-node model cannot see. This is precisely what the ablation ladder measures.
- Compatible classes form large bicliques → cap or sample neighbors per class (GraphSAGE-style neighbor sampling; cap is a tuned hyperparameter).

Optional second relation for ablation only: `shared_CPE` (CVEs sharing a vulnerable product, built from NVD CPE configurations — global, like the label — not from scans).

## 4. Task & labels

- **Task**: node-level regression. Target: `logit(EPSS)` (raw EPSS is extremely right-skewed: median ~0.001, tail to 0.99). Loss: MSE in logit space.
- **Metrics**: Spearman ρ (primary — ranking is what practitioners consume), MAE in probability space (secondary).
- **Labels**: FIRST API `https://api.first.org/data/v1/epss` (already integrated: `nvd_fetcher.py:34`, Mongo cache, 7-day TTL). Every training run stamps the **EPSS model date** (returned per API response) into the model artifact. Historical snapshots (`?date=YYYY-MM-DD`, daily since 2021) enable the D+30 stability evaluation without any time-series machinery.

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

**Split**: plain random split over deduplicated CVE nodes. After D3 (dedup), the duplicate-leakage problem is gone and group-splitting is unnecessary. Keep one **leakage sentinel** anyway: `assert len(train_cves & test_cves) == 0` on `original_cve` sets — one line, catches future regressions if dedup is ever accidentally dropped.

**Transductive masking**: the full graph participates in message passing; loss and metrics are computed only on the respective split's nodes. Test labels never enter the loss.

**The baseline ladder** (each rung isolates one claim):

| Rung | Model | What beating the previous rung proves |
|---|---|---|
| 1 | XGBoost on own features (CVSS + CWE + CPE + age) | baseline; roughly reproduces "EPSS from static features" |
| 2 | XGBoost + enables-graph centralities (in/out-degree, PageRank) as extra tabular features | *position in the chain network carries signal* — already a publishable sentence |
| 3 | GNN on the enables graph | full message passing adds value beyond two centrality numbers |
| 3b (ablation) | GNN + `shared_CPE` second relation | product co-location adds anything on top |

If rung 3 does not beat rung 2 by a meaningful Spearman margin, that negative result is itself informative (and rung 2's centralities still power the residual visualization).

**Additional evaluation regimes**:
- **Label-density stratification**: report test metrics bucketed by fraction of train-labeled neighbors (0% / <50% / ≥50%). Measures how much the transductive setting inflates results vs. the cold-start production case.
- **Drift robustness** (uses D1's per-date models): train on EPSS date D, evaluate on labels from D+30. Quantifies how fast a static model goes stale — informs the retraining cadence.

## 7. Data / corpus

Because the graph and label are both global (D3, D5), the corpus is **not limited by Trivy scans**. Options in order of scale:

1. **Scan-derived corpus** (start here): union of unique CVEs across the 9-image examples corpus (+ any new scans). Small (~1–2k unique CVEs) but the pipeline exists end-to-end today.
2. **Extended scan corpus**: Trivy-scan ~100–200 popular Docker Hub images (automatable; ingest pipeline exists). ~5–15k unique CVEs, same distribution as production use.
3. **Full NVD corpus**: all CVEs with CVSS v3 vectors (~200k). Only needed if rung-3 results look promising and data-hungry; requires bulk NVD ingest rather than per-CVE fetch.

## 8. Stages

Modeled on the metrics-roadmap staging. Each stage lands independently with tests.

- **Stage GML-0 — Corpus exporter.** Backend: dedup by `original_cve`, assemble features, compute enables edges from VC matching, emit versioned JSON. Unit tests on a synthetic mini-corpus (known keys → known edges). *Acceptance: export is deterministic (stable hash) for a fixed cache state.*
- **Stage GML-1 — Labels + tabular baseline.** EPSS labels with model-date stamp; XGBoost rungs 1–2; leakage sentinel; metrics report (Spearman/MAE). *Acceptance: rung-1 Spearman documented; rung-2 vs rung-1 delta documented.*
- **Stage GML-2 — ML service scaffold.** `ml/` container, docker-compose entry, Scripts, `/train` + `/predict` + `/model/info`, GridFS artifacts. Rung-1/2 models served (GNN not needed to ship the service). *Acceptance: end-to-end train→persist→predict cycle through the API.*
- **Stage GML-3 — GNN.** PyG directed SAGE (2 layers, neighbor sampling with biclique cap), rung 3 (+3b ablation). Label-density stratification report. *Acceptance: ladder table complete; go/no-go call on graph ML recorded here.*
- **Stage GML-4 — Residual overlay in PAGDrawer.** Frontend: color CVE nodes by residual (diverging palette), tooltip shows predicted vs actual vs model date. Works with whatever the best available rung is. *Acceptance: overlay toggling documented in StatisticsModal/DebugOverlay docs.*
- **Stage GML-5 — Drift study (optional).** Per-date model matrix (train D, eval D+Δ) using FIRST historical snapshots; retraining-cadence recommendation.

Decision gate after GML-3: if graph rungs don't pay, GML-4 still ships on rung 2 and GML-5 becomes the more interesting writeup.

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
