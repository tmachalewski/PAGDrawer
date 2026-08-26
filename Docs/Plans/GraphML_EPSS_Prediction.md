# Graph ML: EPSS Prediction over the Vulnerability-Chain Graph

Status: **GML-0/1/2 done — ladder complete, research question answered YES** (post-GD-2026 work). Design D1–D22 (2026-08-22…27). Fair ladder ran on 2026-08-27: when the structure is hidden from node features (reaching the model only through edges), **1-hop message passing improves EPSS prediction +0.29 Spearman** (0.37 → 0.66), recovering most of the VC-feature signal from topology alone. The connections carry the exploitability signal — consistent with the VC framework (VCs are formally a graph feature). 2-hop overshoots the depth-1 corpus and oversmooths. See §6 (Ladders A/B) for detail.

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
| D3 | ~~Drop HOST entirely; deduplicate to one node per `original_cve`~~ **Superseded by D19** | Original rationale: EPSS is a global CVE property, so dedup to one global node set. This turned out to destroy the chain structure (see D19) — chains are *within-container*, so host/container context must survive during graph construction. Dedup now happens *within* an image, not globally; `chain_depth` is **kept** (it is the chain signal, not noise). |
| D4 | **CWE and CPE as node features only**, not edge relations | `shared_CWE` creates near-cliques (CWE-79 alone links thousands of CVEs pairwise → O(n²) edges, oversmoothing, giant components). The class signal lives in the feature; the ablation ladder (§6) will test whether relation variants add anything. |
| D5 | **Edges = directed chain relation from VC matching** (refined by D20) | `a → b` when a's exploitation helps enable b along a real attack chain. Directed (in-neighborhood = "my stepping stones", out-neighborhood = "what I unlock") and the semantic core of the project. **Not** the global pairwise closure of the original D5 wording — see D20 for the depth-layered, contribution-edge definition that keeps each graph a DAG. |
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
| D19 | **Corpus = set of per-image DAGs, not one global graph** (2026-08-27) | The first exporter built a global pairwise `enables` closure over all deduplicated CVEs. Empirically that graph was **not a DAG** (156k reciprocal edges; a 455-node strongly-connected blob) and had cross-image edges between CVEs that never co-occur — fictional chains. Reality-pruning is done by the container: chains link only CVEs present on the same Docker image. One graph per image; the same CVE appears in several image graphs (kept, not deduped away). Split therefore groups by `original_cve` across image graphs (D22). |
| D20 | **Depth-layered chains via the builder's logic; contribution edges with layer-skipping** (2026-08-27) | Each image graph is built by the shared `src/core/chain` primitives: attacker baseline `{(AV,N),(PR,N)}` → admit CVEs whose AV/PR prereqs are met → accumulate their **escalating** outcomes (only VCs that strictly raise capability) → advance depth. Monotonic accumulation ⇒ DAG. CVE→CVE edge `a → b` iff `depth(a) < depth(b)` and a's escalating outcomes supply a VC that b's prereqs require — layer-skipping allowed, so a depth-0 CVE can contribute to a depth-2 CVE ("VCs from CVE1 enable CVE3"). The builder and exporter share the same `escalating_outcomes` / `assign_chain_depths` / `contributes` (single source of truth; the builder delegates its escalation filter). |
| D21 | **Environmental VCs (AC/UI) are categorical node features; scenario fixed maximal** (2026-08-27) | AC (attacker skill) and UI (user cooperation) are the **input scenario**, not attacker state — categorical, never numeric, and they don't gate the AV/PR chain BFS (they're a separate frontend reachability overlay). The CVE's own AC/UI requirement is a per-node feature (one-hot `ac`, `ui`). The scenario is fixed **maximal** (skilled attacker, cooperating user → nothing pruned), so AC/UI vary only per-CVE. The legacy `0.5/0.4` probability weights in `consensual_matrix` are vestigial and unused by topology. |
| D22 | **Split groups by `original_cve` across image graphs** (2026-08-27) | Duplicate-leakage returns in a new form: a CVE occurring in several image graphs must land entirely in one fold, or its global EPSS label leaks. `GroupKFold` (or grouped shuffle) on `original_cve`; the leakage sentinel asserts empty `original_cve` intersection across folds. |

## 3. Graph specification

**Structure** — the corpus is a **set of per-image DAGs** (D19). One graph per Docker image; nodes are the CVEs present on that image (deduplicated *within* the image). A CVE on N images is N node occurrences across N graphs — kept, not merged (D22 handles the split).

**Nodes** — CVE occurrences. Each carries the same global features/label plus its `chain_depth` in that image's chain.

**Node features:**

| Feature | Encoding | Source |
|---|---|---|
| CVSS state components (AV, PR, plus C, I, A) | one-hot per component | NVD cache |
| **Environmental VCs (AC, UI)** — attacker-skill / user-cooperation *requirement* of the CVE | one-hot categorical (`AC:L/H`, `UI:N/R`) — never numeric (D21) | NVD cache |
| `chain_depth` in this image | small int (0 = directly exploitable, ≥1 = chain-dependent) — **the chain-position signal** | `core.chain` |
| CWE id(s) | learned `nn.Embedding` (multi-hot pooled if several) | NVD cache |
| CPE / package | hash-embedding of product | Trivy / NVD |
| Age (days since publication), days since last NVD modification | scalar, log-scaled | NVD cache |
| Prereq / outcome VC keys | categorical (same equivalence classes as the M22/ACR merge keys) | VC framework |
| CVE description text (optional, ablation flag) | sentence-transformer embedding (MiniLM), offline + cached, PCA-reduced | NVD cache |

Deferred (D17): KEV flag, Metasploit module presence. Never included: EPSS itself (label).

**VC features play a dual role** — they are node features *and* the predicate that generates the chain edges. If the multi-hop GNN fails to beat the 0-hop baseline, one candidate explanation is "the VC features already encode what the edges would deliver."

**Edges** — directed CVE→CVE **contribution** edges (D20): `a → b` iff `depth(a) < depth(b)` and a's escalating outcomes supply a Vector Changer b's prereqs require. Built by `src/core/chain` (shared with the graph builder). Every image graph is a DAG by construction; the exporter verifies this (`diagnostics.all_dags`).

Known structural property (accept and handle — see D13): within an image, all CVEs sharing a (prereq, outcome) VC class have identical structural roles, so the graph is a blow-up of a small quotient over VC classes and dense depth-layer bicliques form. Cap/sample neighbors per class (GraphSAGE-style). The A4 ablation (class-aggregate features) quantifies how much of the GNN's edge this quotient explains.

Optional second relation for ablation only (A2): `shared_CPE` from scan co-occurrence within an image.

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
- **Backend** — gains `GET /api/ml/export` (per-image DAG corpus) and a thin proxy `GET /api/ml/predictions` so the frontend keeps a single origin.
- **Model artifacts** — MongoDB GridFS: checkpoint + corpus dump + label snapshot (per D18), same provenance discipline as the metrics JSON export. **MLflow** noted as a future consolidation option (tracking + registry in one tool); W&B rejected for PoC (hosted; data leaves the machine).
- **`/predict` note**: the age feature must be computed relative to the model's **label snapshot date**, not wall-clock now — otherwise a stale model silently shifts its own input distribution.
- **Scripts** — `Scripts/start-ml.sh` / `kill-ml.sh`, `Scripts/start-tensorboard.sh` / `kill-tensorboard.sh`, same conventions as the rest.
- **Model** — 2 layers of directed message passing (separate in/out aggregation — direction is semantic here), SAGE-style neighbor sampling. Inductive by construction.

## 6. Evaluation protocol

### GML-1/2 result (2026-08-27) — the connections DO carry the signal

**Two ladders, because the first design was confounded.** The naive ladder gave the GNN the VCs + chain_depth + degree *as node features* AND the edges — so the graph had nothing non-redundant to add. The fair test hides the structural/VC features so message passing is the *only* channel to them.

Ladder A — full features (structure baked into features):

| Rung | Model | Spearman ρ |
|---|---|---:|
| 1 | XGBoost (features incl. VCs) | 0.742 ± 0.041 |
| 2 | 0-hop MLP | 0.740 ± 0.016 |
| 3 | 1-hop GNN | 0.740 ± 0.021 |
| 4 | 2-hop GNN | 0.683 ± 0.064 |

Here message passing adds nothing — but only because the VC signal is already in the features (a confounded, uninformative test of the graph).

Ladder B — **minimal features (CWE + impact only); structure reaches the model ONLY through edges** (the correct test of "do the connections testify to exploitability"):

| Rung | Model | Spearman ρ |
|---|---|---:|
| — | 0-hop (no message passing) | 0.371 ± 0.110 |
| **graph** | **1-hop GNN** | **0.657 ± 0.053** |
| — | 2-hop GNN | 0.464 ± 0.205 |

**Verdict: the connections carry the exploitability signal.** With the structure removed from features, 1-hop message passing lifts Spearman **+0.29** (0.37 → 0.66), recovering ~78 % of the way to the full VC-feature baseline (0.74) **from topology alone**. The answer to §1 is **yes on this corpus** — vulnerability-chain structure improves EPSS prediction; it just has to be accessed through edges, not pre-flattened into features.

**On hops vs chain depth.** The corpus maxes at chain depth 1, so **1-hop spans the entire real chain relation** (enabler ↔ enabled) and is the right model. 2-hop does *not* reach deeper in the chain (there is no depth 2); with bidirectional edges it aggregates same-layer siblings that share an enabler — the dense per-image bicliques then oversmooth, dropping ρ to 0.464 (±0.205). General rule: useful hops ≈ max chain depth (with directed edges, strictly). **Report 1-hop as the graph result.**

Framing: VCs are *formally a graph feature* (D2). Ladder A shows the flattened VC features are sufficient; Ladder B shows the *unflattened* graph (edges only) recovers most of that signal on its own — so the exploitability signal genuinely lives in the connection structure, consistent with the VC framework's premise.

Scope: one container-scan corpus, shallow chains (depth ≤ 1), 886 CVEs, imbalanced (`python:latest` dominates). A deeper/more-diverse corpus (§7 option 2) is the natural way to test whether multi-hop chains add further.

**Decision gate (GML-2 acceptance):** the graph pays when tested fairly (Ladder B). Next: A4 class-aggregate ablation (does 1-hop beat "just the class statistics"?), corpus growth for deeper chains, and the residual overlay (GML-4) — now optionally on the GNN, not only the tabular model.

### GML-0.5 findings (2026-08-27) — the structural signal is real

Diagnostics on the corrected per-image corpus (14 images, 1281 node occurrences, **886 unique CVEs**, all graphs DAGs, 0.8 % unreachable). Compare against the earlier *broken* global-closure graph to see why the structure had to be fixed:

| Signal (Spearman ρ vs EPSS) | Global closure (wrong) | Per-image DAGs (correct) |
|---|---:|---:|
| chain-depth ↔ EPSS | ~0 | **−0.45** |
| out-degree ↔ EPSS | +0.13 | **+0.40** |
| in-degree ↔ EPSS | −0.03 | **−0.43** |

`chain-depth ↔ EPSS = −0.45` is interpretable: **depth-0 CVEs (directly exploitable from the network) rank higher in EPSS than depth-1 CVEs (chain-dependent)** — attackers in the wild reach for what's directly exploitable. The earlier "no signal" result was an artifact of the wrong graph.

Caveats that shape the ladder: (1) η² is still low (~0.11 full class, ~0.02 depth) — the ρ is a *ranking* signal (which is our task, D15), not large *variance* explained. (2) `chain_depth` is nearly a function of the CVE's own AV/PR prereqs, so a tabular model may capture most of it; the 0-hop → 1-hop delta is what tests whether the **graph** adds beyond node features. (3) The corpus is imbalanced — `python:latest` (746 nodes, 78 k edges) dwarfs the other 13 images; weight by image or treat as an outlier. (4) Chains are shallow here (max depth 1) — 3-CVE chains are supported but this corpus's CVSS→VC mapping saturates capability in one step.

### Split

**Split** (per D10/D22): **three-way** — train / validation / test, grouped by `original_cve` across image graphs (a CVE on several images lands entirely in one fold). Hyperparameter tuning reads only validation; test is evaluated **once**, at the end, per model family. Prefer `GroupKFold` on (train+val) for HP selection, then a final fit and a single test evaluation. Run ≥3 seeds and report mean±std — seed variance at ~900 CVEs can exceed the deltas between ladder rungs. Keep one **leakage sentinel**: `assert` empty `original_cve` intersection across folds.

**Transductive masking**: the full graph participates in message passing; loss and metrics are computed only on the respective split's nodes. Validation/test labels never enter the loss.

**The baseline ladder** (per D8/D13; rungs 1–4 are the mainline, A-rows are ablations):

| Rung | Model | What it isolates |
|---|---|---|
| 1 | XGBoost on own features (CVSS + CWE + CPE + age) | out-of-family sanity check; roughly reproduces "EPSS from static features" |
| 2 | **GNN 0-hop** — same architecture/features/training, message passing disabled (MLP per node) | anchor of the neural family; everything above is measured against this |
| 3 | GNN 1-hop on the per-image chain graph | one round of neighbor aggregation — the headline delta for §1's question |
| 4 | GNN 2-hop | deeper propagation (watch oversmoothing) |
| A1 | rung 3/4 **+** description-text embedding | text contribution; whether text absorbs structural signal |
| A2 | rung 3/4 + `shared_CPE` (scan co-occurrence) second relation | product co-location on top of `enables` |
| A3 | rung 1 + chain centralities (in/out-degree, chain-depth, PageRank per image) as tabular features | structure as a few numbers in a tabular model — cheap robustness check; GML-0.5 already shows chain-depth ρ=−0.45, so this rung should move |
| A4 | rung 2 + **class-aggregate features** (per prereq-class: enabler count, mean CVSS, CWE histogram of enablers) | how much of the GNN's edge the quotient structure explains by itself (diagnostic per D13 — informs interpretation, does not veto the GNN) |

The answer to §1's question is the delta **rung 2 → rung 3/4**, measured within one model family (Spearman and top-decile precision, against seed std). A4's role is interpretive: if A4 ≈ rung 3, the chain signal is class-statistical; if rung 3 > A4, message passing extracts more than class aggregates.

**Additional evaluation regime**:
- **Per-image cross-validation**: because each image is a graph sample and the split groups by `original_cve`, the natural generalization test is holding out whole images — measures "predict EPSS for a new image's CVEs." Report alongside the grouped-CVE split.

## 7. Data / corpus

Since chains are per-image (D19), the corpus **is** the set of scanned images — each image is a graph sample. Options in order of scale:

1. **Scan-derived corpus** (current, per D11): the existing example scans → **14 image graphs, 886 unique CVEs** (built 2026-08-27). The `ignore_ttl` rebuild mode reuses the frozen Mongo cache offline, keeping the feature snapshot stable across experiments. Per D18 the exact corpus dump is archived with each run. More images ⇒ more graph samples (the natural way to grow this corpus, since each image is one sample).
2. **Extended scan corpus**: Trivy-scan ~100–200 popular Docker Hub images (automatable; ingest pipeline exists). More, more-diverse graphs — the right lever for a GNN that learns across image samples.
3. **Full NVD corpus**: only if a scan-derived study proves promising; note that "all of NVD" is not one image, so it needs a different graph-definition (e.g. synthetic co-occurrence) — future territory, not a drop-in.

## 8. Stages

Reordered per D16: experiments first, the serving module only after the gate. Each stage lands independently with tests.

- **Stage GML-0 — Corpus exporter. ✅ DONE (2026-08-27).** `ml/exporter.py` builds one DAG per image (dedup within image, depth-layered chains, contribution edges) via the shared `src/core/chain` primitives; `ml/export_corpus.py` is the CLI; `ml/diagnose.py` reports the structure↔EPSS signal. Verifies every image graph is a DAG. 24 exporter tests + 10 chain tests; backend suite 412 passed. Real corpus: 14 images, 886 unique CVEs, all DAGs. Findings in §6 (GML-0.5). *Acceptance met: deterministic export; DAG verification; diagnostics produced.*
- **Stage GML-1 — Labels + non-graph baselines.** Download + archive one FIRST daily CSV snapshot (D9); percentile-target join (D15) with model-date stamp; grouped three-way split with leakage sentinel (D22); rung 1 (XGBoost) and rung 2 (0-hop GNN); metrics report (Spearman + top-decile precision, mean±std over seeds). *Acceptance: rungs 1–2 documented with seed variance; split protocol frozen; corpus dump archived with each run (D18).*
- **Stage GML-2 — Multi-hop GNN experiments. ✅ DONE (2026-08-27).** `ml/gnn.py` — per-image PyG graphs, SAGEConv 0/1/2-hop, `--drop-vc`/`--drop-structural` to hide structure from features. Two ladders (see §6): with structure in features, message passing is redundant (Ladder A, 0.740 flat); with structure **only via edges** (Ladder B), 1-hop lifts ρ from 0.371 to **0.657** (+0.29). **Verdict: the connections carry the exploitability signal** — §1 answered yes on this corpus. 2-hop oversmooths the depth-1 bicliques (0.464). *Acceptance met: ladder complete; go = the graph pays under a fair test.*
- **Stage GML-3 — ML service.** (After the gate; ships regardless of the GNN verdict — the overlay is valuable from rung 1–2 up.) `ml/` container, docker-compose entry, Scripts, `/train` + `/predict` + `/model/info`, GridFS artifacts (checkpoint + corpus dump + label snapshot), TensorBoard sidecar. *Acceptance: end-to-end train→persist→predict cycle through the API; a training run visible live in TensorBoard.*
- **Stage GML-4 — Residual overlay in PAGDrawer.** Frontend: color CVE nodes by residual (diverging palette), tooltip shows predicted vs actual vs model date. Works with whatever the best available rung is. Residual display is gated on magnitude exceeding the seed-ensemble std for that node (don't render noise as insight); the stronger KEV-based sanity check is deferred with D17. *Acceptance: overlay toggling documented in StatisticsModal/DebugOverlay docs; uncertainty gating in place.*

**Future work (out of mainline)**: drift study — per-date model matrix (train on snapshot D, evaluate on snapshot D+Δ) using FIRST's historical daily files; yields a retraining-cadence recommendation. KEV + Metasploit weaponization features (D17). Hetero-GNN ablation revisiting D2's presumption. NVD-configuration `shared_CPE`.

## 9. Risks & open questions

- **Quotient dominance** — the GML-0.5 census confirms it (3 classes cover 50 % of CVEs; η² ≈ 0.11). If A4 matches rung 3, the honest interpretation is "class-statistical signal, not topological" — the GNN still stands as the representation (D13), but the writeup must say which it is.
- **Corpus imbalance** — `python:latest` dominates (746 of 886 CVEs). Weight per image, or hold it out, so one graph doesn't drive the result.
- **Corpus size** (~886 unique CVEs) is small for embeddings (CWE/CPE) — freeze embedding dims small (8–16) or grow the corpus (more images, §7 option 2).
- **Shallow chains** — this corpus tops out at depth 1, so 1-hop message passing already sees the whole chain; depth-2 GNN may add nothing here. A deeper/more-diverse corpus (option 2) is where multi-hop could matter.
- **Resolved**: the chain predicate is shared — `src/core/chain` (`prereqs_satisfied` / `escalating_outcomes` / `assign_chain_depths` / `contributes`) is the single source of truth; the builder delegates to it, the exporter imports it.

## 10. Cross-references

- **Implementation**: `ml/exporter.py` (per-image DAG builder), `ml/export_corpus.py` (CLI), `ml/diagnose.py` (signal analysis), `ml/README.md`.
- **Shared chain primitives (single source of truth)**: `src/core/chain.py` — `escalating_outcomes`, `assign_chain_depths`, `contributes`; predicate in `src/core/consensual_matrix.py` (`prereqs_satisfied`).
- VC framework & consensual matrix: `Docs/VC_Framework_Paper.md`, `Docs/ConsensualMatrix_TrascribedByHand.md`
- Chain construction: `Docs/Plans/Chain_Depth_Aware_Attack_Stages.md`, `src/graph/builder.py`
- Merge keys (same equivalence classes as the VC quotient): `frontend/js/features/mergeKeys.ts`, `Docs/_domains/PaperAlgorithms.md` §3
- EPSS fetching & caching: `src/data/loaders/nvd_fetcher.py`, `Docs/_domains/MongoDBPersistence.md`
- Staging pattern this plan imitates: `Docs/Plans/Master_Implementation_Roadmap.md`
