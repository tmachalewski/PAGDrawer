# Graph ML: EPSS Prediction over the Vulnerability-Chain Graph

Status: **planned** (post-GD-2026 work). Initial design settled 2026-08-22; amendments D8–D12 on 2026-08-24/25; critique-driven revision D13–D18 on 2026-08-26 (research question reframed, loss chosen, stages reordered experiments-first).

---

## 1. Research question

> **Does vulnerability-chain information improve EPSS prediction?**

Concretely: given a CVE's own attributes (CVSS vector, CWE, package, age), does adding the `enables` chain structure — which CVEs can serve as stepping stones into it, and what it unlocks — measurably improve prediction of its EPSS score? The chaining relation ("outcomes of *a* satisfy prerequisites of *b*") is the project's own VC-framework contribution, so this question is unique to PAGDrawer.

This is deliberately a **prediction-utility** question, not a behavioural claim about attackers. A positive result says "chain context carries incremental predictive signal"; it does not by itself establish *why* (confounders like product popularity flow through both EPSS and the chain structure). The behavioural question is out of scope for this plan.

Secondary, practical payoffs:

- **EPSS imputation** for fresh/unscored CVEs.
- **Residual visualization** in PAGDrawer: color CVE nodes by `predicted − actual` EPSS. Nodes the structure "believes" should be hotter or colder than FIRST says are exactly what an analyst should inspect. This ties the ML module back to the tool's core identity — visualization.

## 2. Decision log

These were discussed and settled; do not re-litigate without new evidence.

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Per-date model** (predict EPSS as of a stamped model date), not time-series | PoC simplicity; retrain often. EPSS label MUST carry the FIRST model date. (Amended by D9: labels come from one daily CSV snapshot; the drift study is future work.) |
| D2 | **CVE-centric graph**, not heterogeneous schema graph | In the hetero graph, VC info is 3 hops from CVE (CVE→CWE→TI→VC); a GNN would need ≥3 layers just to see its own outcomes, and deep GNNs oversmooth on small graphs. Chain attributes are folded into CVE node features instead. (Empirical presumption, not measured — a hetero-GNN ablation is legitimate future work despite this log's header.) |
| D3 | **Drop HOST entirely; deduplicate to one node per `original_cve`** | EPSS is a global property of the CVE — identical for every copy across hosts/CPEs. Host context is noise w.r.t. this label. Dedup kills the duplicate-leakage problem at the root (no more group-split machinery needed). Environment-dependent features (`chain_depth`, `layer`, host counts) are dropped with it. |
| D4 | **CWE and CPE as node features only**, not edge relations | `shared_CWE` creates near-cliques (CWE-79 alone links thousands of CVEs pairwise → O(n²) edges, oversmoothing, giant components). The class signal lives in the feature; the ablation ladder (§6) will test whether relation variants add anything. |
| D5 | **Edges = directed `enables` relation from VC matching** | `a → b` iff `outcomes(a) ⊨ prereqs(b)` (consensual matrix). Computable globally from CVE data alone — survives dedup, host-independent like the label, directed (in-neighborhood = "my stepping stones", out-neighborhood = "what I unlock"), and is the semantic core of the project. |
| D6 | **The ML graph is a separate artifact from the visualization graph** | Built from the deduplicated CVE corpus, not from a scan's rendered graph. PAGDrawer re-enters at the end as the lens: residuals overlaid on a concrete environment's attack graph. |
| D7 | **Baseline ladder is mandatory** (§6) | The whole thesis is "structure adds signal beyond local features"; without tabular baselines the GNN result is uninterpretable. |
| D8 | **0-hop GNN is the primary structural baseline** (2026-08-24) | Same architecture / features / optimizer with message passing disabled (an MLP per node). Isolates exactly one variable — edge propagation — which the XGBoost comparison cannot (different model family, capacity, regularization). XGBoost stays as an out-of-family sanity check. |
| D9 | **Labels from FIRST daily CSV snapshots, same-date prediction** (2026-08-24) | `epss_scores-YYYY-MM-DD.csv.gz` — one atomic file = one consistent model date for the whole corpus (API calls spread over time can straddle a model update), no rate limits, archivable next to the model artifact for full reproducibility. Task is pure same-date imputation; the D+30 drift study is demoted to future work. |
| D10 | **Three-way split (train/val/test)** (2026-08-24) | Hyperparameters are tuned — so tuning looks only at validation; test is evaluated once per model family. k-fold CV on train+val for HP selection at this corpus size; multiple seeds, report mean±std (seed variance can exceed rung deltas at ~1–2k nodes). |
| D11 | **Scan-derived corpus first** (2026-08-24) | Confirmed: GML-0/1 build from unique CVEs of the existing scans corpus (§7 option 1). Scale-ups (100+ images, full NVD) only when results justify the cost. |
| D12 | **Text embeddings: local sentence-transformers, not Claude API** (2026-08-24) | The Claude API has no embeddings endpoint (Anthropic recommends third-party providers, e.g. Voyage AI). Local sentence-transformers is deterministic, free, offline, and cacheable — matching the offline-exporter design. Optional variant A1b: use Claude for *feature extraction* from descriptions (classify into tags: RCE / DoS / auth-bypass / attacked component) — sometimes better than raw embeddings at small corpus sizes, but slow, paid, and non-deterministic; ablation-only, never the mainline. |
| D13 | **GNN is the mainline commitment** (2026-08-26) | The quotient-graph property (§3) is acknowledged: `enables` topology is a function of the VC keys. The GNN stays regardless — keeping features attached to the nodes they belong to preserves the *actual vulnerability structure*, and message passing over it is the representation we want to study. The quotient census (GML-0) is a **diagnostic**, not a kill-gate; the class-aggregate ablation (A4) quantifies how much of the GNN's edge the quotient explains, it does not veto the GNN. |
| D14 | **Research question = prediction utility** (2026-08-26) | §1 reframed from "do attackers prefer well-connected CVEs" (behavioural, unanswerable by this design) to "does chain information improve EPSS prediction" (directly answered by the ladder delta rung 2 → rung 3/4). |
| D15 | **Loss: MSE on the percentile-transformed target** (2026-08-26) | Target = EPSS percentile within the label snapshot (mid-rank for ties → uniform [0,1]). Rationale: aligns the loss with the rank-based evaluation metrics; eliminates the floor-mass pathology of raw/logit EPSS (thousands of CVEs tied at ~0.0004 would dominate an MSE-in-logit loss); ties become an explicit plateau instead of a numerical trap. Probability view is recovered exactly by mapping predicted percentiles back through the archived snapshot's empirical CDF (the snapshot is archived per D9, so the mapping is reproducible). |
| D16 | **Experiments before service** (2026-08-26) | GNN experiments run as plain scripts in `ml/` (local TensorBoard, no container) *before* the serving module is built. The FastAPI service, docker-compose entry, and GridFS registry land only after the experiment gate — no infrastructure for a model that may not survive the ladder. |
| D17 | **KEV / Metasploit features deferred** (2026-08-26) | Both are strong known exploitation predictors and cheap to ingest (one JSON each), but they are also heavy inputs to EPSS itself — they boost imputation while diluting the structural question. Parked entirely for now; revisit after the ladder results. The KEV-based residual sanity check is deferred with them. |
| D18 | **Archive the training-corpus dump** (2026-08-26) | The exported corpus (CVE set, features, edges) that participated in each training run is stored alongside the model artifact — not just hashed. A hash can only prove reproduction is impossible after cache mutation; the dump makes it possible. |

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

Not included (dropped with D3): `chain_depth`, `layer`, per-host/per-scan context. Deferred (D17): KEV flag, Metasploit module presence. Never included: EPSS itself (label).

**VC features play a dual role** — they are node features *and* the predicate that generates `enables` edges. Intentional, but it shapes interpretation: if the multi-hop GNN fails to beat the 0-hop baseline, one candidate explanation is "the VC features already encode what the edges would deliver", since topology is a function of these features.

**Text-feature caveat**: EPSS's own model consumes text-derived tags, so description embeddings partially overlap the label's inputs. Fine for imputation quality — but text may absorb structural signal, which is why +text is a separate ablation rung, not part of the base feature set.

**Edges** — directed `enables`: `a → b` iff outcomes(a) satisfy prereqs(b) per the consensual matrix (see `Docs/ConsensualMatrix_TrascribedByHand.md`, chain logic in `src/graph/builder.py`).

Known structural property (accept and handle, don't fight — see D13):
- The relation is a function of (outcome-key, prereq-key) pairs, whose vocabulary is small — the same equivalence classes as the M22/ACR merge keys. The graph is therefore a *blow-up of a small quotient graph* over key classes: all CVEs with the same key pair have identical structural neighborhoods. What the GNN adds over features is **corpus-level statistics of neighbor classes** (which CWEs/packages/labels actually populate "the class that enables me"), which a per-node model cannot see. The A4 ablation quantifies this; the quotient census in GML-0 characterizes it up front.
- Compatible classes form large bicliques → cap or sample neighbors per class (GraphSAGE-style neighbor sampling; cap is a tuned hyperparameter).

Optional second relation for ablation only: `shared_CPE` — for the PoC corpus built from **scan co-occurrence** (same package in the Trivy scans; trivial to compute). The NVD-configuration variant (parsing applicability statements and match ranges) is real parser work and is future-corpus territory, not A2.

## 4. Task & labels

- **Task**: node-level regression. **Target** (per D15): EPSS **percentile within the label snapshot** (mid-rank for ties, scaled to [0,1] — uniform by construction). **Loss**: MSE on this target.
- **Probability view**: predicted percentile → probability via the archived snapshot's empirical CDF (exact and reproducible because the snapshot file is archived, D9). MAE in probability space is reported after this mapping.
- **Metrics**: co-primary — Spearman ρ **and** top-decile precision (share of true top-10 %-EPSS CVEs recovered in the predicted top decile). Secondary: MAE in probability space, optionally NDCG@k. Rationale: the corpus floor is a mass of near-identical scores; ranking quality *at the top* is what practitioners consume, and Spearman alone is unstable under heavy ties.
- **Labels** (per D9): one FIRST **daily CSV snapshot** — `epss_scores-YYYY-MM-DD.csv.gz` (published daily since 2021). One atomic file gives every CVE in the corpus a label from the same model date; the file is archived next to the model artifact for reproducibility. The per-CVE API (`nvd_fetcher.py:34`) remains the source for the *visualization* path; the ML pipeline uses the bulk file. Prediction target is the **same date** as the label snapshot — pure imputation, no forecasting.

## 5. Architecture

Two phases (per D16): **experiment phase** first — plain scripts, no service; **service phase** only after the gate.

**Experiment phase** (stages GML-0…GML-3):

- `ml/` directory with the exporter consumer, training scripts, and eval harness. No container, no API — `venv` + scripts.
- **Training monitoring** — TensorBoard (native PyTorch `SummaryWriter`, no TensorFlow dependency), run locally against `ml/runs/`. Log per epoch: train/val loss, Spearman, top-decile precision, CWE/CPE embedding histograms; the embedding projector comes free.
- Every training run stores (per D18): the model checkpoint, the **corpus dump it trained on** (CVE set + features + edges as exported JSON), the label snapshot file, split assignment, seed, hyperparameters, git SHA, metrics.

**Service phase** (stage GML-4, after the gate):

```
docker-compose:  mongo  +  backend (FastAPI)  +  ml (NEW container)  +  tensorboard (sidecar)
```

- **`ml/` service** — separate FastAPI app with its own image (torch + PyTorch Geometric are heavy; keep them out of the backend image). Endpoints: `POST /train`, `POST /predict`, `GET /model/info` (version, EPSS model date, eval metrics, corpus reference).
- **Backend** — gains `GET /api/ml/export` (deduplicated CVE corpus + enables edges) and a thin proxy `GET /api/ml/predictions` so the frontend keeps a single origin.
- **Model artifacts** — MongoDB GridFS: checkpoint + corpus dump + label snapshot (per D18), same provenance discipline as the metrics JSON export. **MLflow** noted as a future consolidation option (tracking + registry in one tool); W&B rejected for PoC (hosted; data leaves the machine).
- **`/predict` note**: the age feature must be computed relative to the model's **label snapshot date**, not wall-clock now — otherwise a stale model silently shifts its own input distribution.
- **Scripts** — `Scripts/start-ml.sh` / `kill-ml.sh`, `Scripts/start-tensorboard.sh` / `kill-tensorboard.sh`, same conventions as the rest.
- **Model** — 2 layers of directed message passing (separate in/out aggregation — direction is semantic here), SAGE-style neighbor sampling. Inductive by construction.

## 6. Evaluation protocol

**Split** (per D10): **three-way** — train / validation / test over deduplicated CVE nodes. Hyperparameter tuning reads only validation; test is evaluated **once**, at the end, per model family. At this corpus size, prefer k-fold CV on (train+val) for HP selection, then a final fit and a single test evaluation. Run ≥3 seeds and report mean±std — seed variance at ~1–2k nodes can exceed the deltas between ladder rungs. Keep one **leakage sentinel**: `assert len(train_cves & test_cves) == 0` on `original_cve` sets — one line, catches future regressions if dedup is ever accidentally dropped.

**Transductive masking**: the full graph participates in message passing; loss and metrics are computed only on the respective split's nodes. Validation/test labels never enter the loss.

**The baseline ladder** (per D8/D13; rungs 1–4 are the mainline, A-rows are ablations):

| Rung | Model | What it isolates |
|---|---|---|
| 1 | XGBoost on own features (CVSS + CWE + CPE + age) | out-of-family sanity check; roughly reproduces "EPSS from static features" |
| 2 | **GNN 0-hop** — same architecture/features/training, message passing disabled (MLP per node) | anchor of the neural family; everything above is measured against this |
| 3 | GNN 1-hop on the enables graph | one round of neighbor aggregation — the headline delta for §1's question |
| 4 | GNN 2-hop | deeper propagation (watch oversmoothing) |
| A1 | rung 3/4 **+** description-text embedding | text contribution; whether text absorbs structural signal |
| A2 | rung 3/4 + `shared_CPE` (scan co-occurrence) second relation | product co-location on top of `enables` |
| A3 | rung 1 + enables-graph centralities (in/out-degree, PageRank) as tabular features | two numbers of structure in a tabular model — cheap robustness check of the structural signal |
| A4 | rung 2 + **class-aggregate features** (per prereq-class: enabler count, mean CVSS, CWE histogram of enablers) | how much of the GNN's edge the quotient structure explains by itself (diagnostic per D13 — informs interpretation, does not veto the GNN) |

The answer to §1's question is the delta **rung 2 → rung 3/4**, measured within one model family (Spearman and top-decile precision, against seed std). A4's role is interpretive: if A4 ≈ rung 3, the chain signal is class-statistical; if rung 3 > A4, message passing extracts more than class aggregates.

**Additional evaluation regime**:
- **Label-density stratification**: report test metrics bucketed by fraction of train-labeled neighbors (0% / <50% / ≥50%). Measures how much the transductive setting inflates results vs. the cold-start production case.

## 7. Data / corpus

Because the graph and label are both global (D3, D5), the corpus is **not limited by Trivy scans**. Options in order of scale:

1. **Scan-derived corpus** (start here, per D11): union of unique CVEs across the 9-image examples corpus (+ any new scans). Small (~1–2k unique CVEs) but the pipeline exists end-to-end today. The `ignore_ttl` rebuild mode (added 2026-08-24) helps here: old scans can be re-ingested offline against the frozen Mongo cache, keeping the feature snapshot stable across ML experiments without refetching. Per D18, the exact corpus dump used by each run is archived with the run.
2. **Extended scan corpus**: Trivy-scan ~100–200 popular Docker Hub images (automatable; ingest pipeline exists). ~5–15k unique CVEs, same distribution as production use.
3. **Full NVD corpus**: all CVEs with CVSS v3 vectors (~200k). Only needed if rung-3 results look promising and data-hungry; requires bulk NVD ingest rather than per-CVE fetch.

## 8. Stages

Reordered per D16: experiments first, the serving module only after the gate. Each stage lands independently with tests.

- **Stage GML-0 — Corpus exporter.** Backend: dedup by `original_cve`, assemble features, compute enables edges from VC matching, emit versioned JSON. Also emits **diagnostics**: degree histograms, quotient-class census (how many (prereq, outcome)-key classes, membership distribution), isolated-node share. Unit tests on a synthetic mini-corpus (known keys → known edges). *Acceptance: export is deterministic (stable hash) for a fixed cache state; diagnostics report produced.*
- **Stage GML-1 — Labels + non-graph baselines.** Download + archive one FIRST daily CSV snapshot (D9); percentile-target join (D15) with model-date stamp; three-way split with leakage sentinel (D10); rung 1 (XGBoost) and rung 2 (0-hop GNN); metrics report (Spearman + top-decile precision, mean±std over seeds). *Acceptance: rungs 1–2 documented with seed variance; split protocol frozen; corpus dump archived with each run (D18).*
- **Stage GML-2 — Multi-hop GNN experiments.** Plain scripts in `ml/` (no service): PyG directed SAGE (1- and 2-hop rungs, neighbor sampling with biclique cap), ablations A1–A4, local TensorBoard. Label-density stratification report. *Acceptance: ladder table complete; interpretation of A4 vs rung 3 recorded; go/no-go call on the serving investment recorded here.*
- **Stage GML-3 — ML service.** (After the gate; ships regardless of the GNN verdict — the overlay is valuable from rung 1–2 up.) `ml/` container, docker-compose entry, Scripts, `/train` + `/predict` + `/model/info`, GridFS artifacts (checkpoint + corpus dump + label snapshot), TensorBoard sidecar. *Acceptance: end-to-end train→persist→predict cycle through the API; a training run visible live in TensorBoard.*
- **Stage GML-4 — Residual overlay in PAGDrawer.** Frontend: color CVE nodes by residual (diverging palette), tooltip shows predicted vs actual vs model date. Works with whatever the best available rung is. Residual display is gated on magnitude exceeding the seed-ensemble std for that node (don't render noise as insight); the stronger KEV-based sanity check is deferred with D17. *Acceptance: overlay toggling documented in StatisticsModal/DebugOverlay docs; uncertainty gating in place.*

**Future work (out of mainline)**: drift study — per-date model matrix (train on snapshot D, evaluate on snapshot D+Δ) using FIRST's historical daily files; yields a retraining-cadence recommendation. KEV + Metasploit weaponization features (D17). Hetero-GNN ablation revisiting D2's presumption. NVD-configuration `shared_CPE`.

## 9. Risks & open questions

- **Quotient dominance** — if the census (GML-0) shows a handful of key classes covering most nodes, and A4 matches rung 3, the honest interpretation is "class-statistical signal, not topological" — the GNN still stands as the representation (D13), but the writeup must say which it is.
- **Corpus size at stage 1** (~1–2k CVEs) is small for embeddings (CWE/CPE) — freeze embedding dims small (8–16) or defer hash-embeddings to corpus option 2.
- **CVEs without CVSS v3 vectors** have no prereq/outcome keys → isolated nodes. Report their share (GML-0 diagnostic); they still work in tabular rungs.
- **Open**: exact satisfaction semantics of `outcomes(a) ⊨ prereqs(b)` for edge construction — reuse the backend chain-building predicate from `src/graph/builder.py` verbatim (single source of truth), do not re-derive in the exporter.

## 10. Cross-references

- VC framework & consensual matrix: `Docs/VC_Framework_Paper.md`, `Docs/ConsensualMatrix_TrascribedByHand.md`
- Chain construction: `Docs/Plans/Chain_Depth_Aware_Attack_Stages.md`, `src/graph/builder.py`
- Merge keys (same equivalence classes as the enables quotient): `frontend/js/features/mergeKeys.ts`, `Docs/_domains/PaperAlgorithms.md` §3
- EPSS fetching & caching: `src/data/loaders/nvd_fetcher.py`, `Docs/_domains/MongoDBPersistence.md`
- Staging pattern this plan imitates: `Docs/Plans/Master_Implementation_Roadmap.md`
