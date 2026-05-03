# Paper Evaluation Metrics — Implementation Plan

**Created:** 2026-05-03-19-42
**Branch (proposed):** `feature/paper-metrics`
**Source plan:** `Docs/Plans/metric_proposals.md` § "How I would prioritise"
**Sister plan:** `Docs/Plans/Debug_Overlay_Visualizations.md` — visualization-priority ordering (the "what looks good on the graph" set)

> ⚠️ **Scope axis: paper importance, not visualization.** This plan picks the metrics the GD 2026 reviewers will look for in your evaluation table — regardless of whether they have a natural overlay. Metrics that visualize well but aren't in the recommended evaluation set live in the sister plan.

---

## Goal

Implement all 12 metrics from the recommendation set in `metric_proposals.md` § "How I would prioritise":

- **5 body-of-paper metrics** (the "if you can implement five" tier): M1, M2, M14, M20, M25
- **7 appendix-only metrics** (the next tier): M11, M12, M19, M22, M24, M26, M28

Every metric ends up as a CSV column. Visualizations are added only where they're cheap and natural (overlap with the sister plan); otherwise the metric is **CSV-only** and inspected as a number in the Statistics modal.

The metrics deliberately **excluded** from this plan (per the "How I would prioritise" section's "would NOT pursue" guidance): **M6 Symmetry, M7 Edge Continuity, M29 Information Density**.

---

## Decisions Locked In

| # | Choice | Why |
|---|--------|-----|
| 1 | Scope: 12 metrics from the recommendation set — M1, M2, M11, M12, M14, M19, M20, M22, M24, M25, M26, M28. | Mirrors the paper-importance prioritization in `metric_proposals.md`. |
| 2 | All computation in the browser (`frontend/js/features/metrics.ts`). | Same rationale as the sister plan; metrics modal already runs in the browser. |
| 3 | Every metric appears in the CSV. Visualizations only where the sister plan covers them. | The paper consumes CSV; overlays are bonus, not a requirement. |
| 4 | M11 and M12 (k-NN preservation, trustworthiness) are CSV-only — no per-node interactive overlay in this plan. | Per-node overlays require interaction work that's deferred to a future plan. |
| 5 | Implementation order: body metrics first (M1 → M2 → M14 → M20 → M25), then appendix metrics (M19 → M24 → M26 → M22 → M28 → M11 → M12). | Body metrics unblock the paper; appendix metrics polish it. |
| 6 | Backend changes only for M19 (chain_length) and M14 (compound expansion in reachability — implementable frontend-only with care). | Minimize backend churn. |
| 7 | M1 Stress uses BFS-based APSP for unweighted graphs (matches PAGDrawer's edge model). | Dijkstra unnecessary; BFS is simpler and faster. |

---

## Overlap with the Sister Plan

Metrics that appear in **both** plans — work done in either plan satisfies both:

| Metric | Where covered in sister plan | Notes |
|--------|------------------------------|-------|
| M2 Crossing angle | Phase 2 | Visualization adds value; do it in the sister plan |
| M19 Bridge contraction depth | Phase 3 (with backend wiring) | Same |
| M20 Edge consolidation ratio | Phase 3 | Same |
| M24 Column purity | Phase 4 | Same |
| M25 Type-pair crossings | Phase 2 | Same |

If both plans run, these five are implemented once. If only this plan runs, the sister-plan visualization for these five is dropped (CSV-only here).

Metrics **unique to this plan** (no overlay needed; CSV-only):

- M1 Stress
- M11 Neighborhood preservation (k-NN overlap)
- M12 Trustworthiness & continuity
- M14 Reachability preservation rate
- M22 Attribute compression ratio
- M26 Edge-type distribution
- M28 Visual clutter score

---

## Per-Metric Implementation Entries

Effort estimates assume the sister plan **has not** been implemented (so the five overlapping metrics carry their full visualization cost too). If sister plan ships first, subtract roughly 8 hours from this plan.

---

### M1 — Stress (~5 hours)

**Why it matters**: the most-cited GD layout-quality metric. Reviewers expect it.

- **CSV column**: `stress_per_pair`
- **Algorithm**:
  1. Compute APSP on the visible graph via BFS from each node — O(|V|·(|V|+|E|))
  2. Treat the graph as undirected for distance computation (matches Purchase 2002)
  3. For each reachable pair (i, j), compute `(‖p_i − p_j‖_logical − d_ij)²`
  4. Sum, divide by the count of reachable pairs (skip unreachable, report the count separately as `stress_unreachable_pairs`)
- **Disconnected-graph convention**: skip-and-report (per the plan's Implementation Notes section)
- **Performance**: for the largest example (~830 nodes), APSP is ~830 BFS runs. Use `cy.elements().bfs()` or maintain a sparse adjacency in a `Map<string, string[]>`. Roughly 100–300 ms on the largest graph; acceptable for a per-snapshot computation behind a "compute" button rather than auto-refresh.
- **Overlay**: ❌ none in this plan (sister plan has it as ⚠️ — defer)
- **CSV columns**: `stress_per_pair`, `stress_unreachable_pairs`
- **Tests**: known-layout sanity checks; trivial-graph edge cases (1 node, 2 nodes)
- **Risk**: APSP performance at the high end of the graph-size distribution. Mitigation: lazy compute (only on Statistics modal open or CSV export click), with a small spinner if it takes > 300 ms.

---

### M2 — Crossing Angle (~2 hours, shared with sister plan)

**Why it matters**: Huang et al. (2014) — "larger crossing angles make graphs easier to read". Path-tracing performance directly correlates with crossing angle.

- **CSV columns**: `crossings_mean_angle_deg`, `crossings_min_angle_deg`, `crossings_right_angle_ratio`
- **Algorithm**: extend `findCrossings()` so each `CrossingInfo` carries `angle: number` (radians). Compute via `arctan2(|cross|, |dot|)` of edge direction vectors at the crossing point.
- **Overlay**: ✅ — see sister plan Phase 2. Skip if sister plan does not run.
- **Effort**: 2 hours total; 1.5 hours of the 2 are the math + CSV + tests; the visualization adds 30 min
- **Tests**: K4-in-a-square has crossing at exactly 90°; mean of two perpendicular crossings = 90°

---

### M11 — Neighborhood Preservation (k-NN Overlap) (~3.5 hours)

**Why it matters**: quantifies whether your reductions trade neighborhood faithfulness for compactness — directly relevant to compound merging.

- **CSV columns**: `np_k5`, `np_k10`, `np_k20` (three values of k)
- **Algorithm** (per `metric_proposals.md` M11):
  1. Reuse APSP from M1 — no extra cost
  2. For each node v: top-k graph neighbors `N_k^G(v)` (k smallest finite `D[v][·]`); top-k layout neighbors `N_k^L(v)` (k smallest Euclidean from `pos[v]`)
  3. NP_k(v) = |N_k^G(v) ∩ N_k^L(v)| / k
  4. Average across nodes with ≥ k reachable neighbors; report `np_k_excluded` count
- **Overlay**: ❌ none (per-node, on-click overlay deferred to a future "interactive diagnostics" plan)
- **Effort**: 3.5 hours — k-NN selection (1h), three k values (30m), tests (1.5h), CSV (30m). Cheaper if M1 ships first (APSP shared).
- **Risk**: k-NN at three values triples the computation but APSP cost dominates anyway

---

### M12 — Trustworthiness and Continuity (~2.5 hours)

**Why it matters**: decomposes M11's error into "false friends" and "missing friends" — diagnoses *what kind* of neighborhood violation the merge mechanism causes.

- **CSV columns**: `trust_k10`, `cont_k10` (single k = 10 to keep CSV manageable)
- **Algorithm** (per `metric_proposals.md` M12): same APSP + layout-distance setup as M11, but with rank-weighted asymmetric sums. Use Venna & Kaski 2001's formula.
- **Overlay**: ❌ none
- **Effort**: 2.5 hours — formula coding (1h), tests (1h), CSV (30m). Cheaper if M11 ships first (APSP and ranks shared).

---

### M14 — Reachability Preservation Rate (~3 hours)

**Why it matters**: empirically validates the bridge-edge soundness proposition. A 100% rate closes the proof-vs-implementation gap. Reviewers love empirically-validated theory.

- **CSV column**: `reachability_preservation_rate`
- **Algorithm** (per `metric_proposals.md` M14):
  1. Sample K = 1000 pairs (u, v) from V' × V' (visible nodes)
  2. For each, BFS from u in G (the unreduced graph) and in G' (the visible graph) treating bridge edges as single hops
  3. For compound parents: expand at the parent level. v is reached in G if any child of v is reached
  4. Average agreement
- **Backend dependency**: needs to access the *unreduced* graph G. The current `/api/graph` returns G' (whatever's after the reductions applied via slider config). Two options:
  - (a) Add a query param `?expand=true` returning the canonical full graph
  - (b) Cache the unreduced graph in the backend at upload time; serve via a new `/api/graph/full` endpoint
- **Recommend (b)** — non-invasive, doesn't risk affecting the existing endpoint
- **Overlay**: ❌ none — expected to be 1.0; nothing to draw
- **Effort**: 3 hours — backend endpoint (1h), frontend BFS (1h), compound expansion logic (30m), tests (30m)
- **Tests**: on the mock data, expected = 1.0 always

---

### M19 — Bridge-Edge Proportion and Contraction Depth (~3 hours, shared with sister plan)

**Why it matters**: tells the reader whether your "bridge edges" represent one collapsed node or chains of five — transparency about how synthetic the reduced graph is.

- **CSV columns**: `bridge_edge_proportion`, `mean_contraction_depth`
- **Backend change**: as in sister plan — `chain_length` on each bridge edge
- **Overlay**: ✅ — sister plan Phase 3
- **Effort**: 3 hours total; CSV portion alone is 1 hour after backend wiring

---

### M20 — Edge Consolidation Ratio (~3 hours, shared with sister plan)

**Why it matters**: per-group compression factor for the merge mechanism — tells the reader whether the merge is concentrated in a few large groups or distributed.

- **CSV column**: `mean_ecr_weighted` (size-weighted mean across all compound parents)
- **Overlay**: ✅ — sister plan Phase 3
- **Algorithm**: count raw incoming/outgoing edges from each compound parent's children versus the synthetic post-consolidation edges
- **Effort**: 3 hours total; CSV portion 1 hour
- **Risk**: only meaningful in outcomes-mode merge — emit `null` outside outcomes mode

---

### M22 — Attribute Compression Ratio (~1.5 hours)

**Why it matters**: the structural upper bound on what the merge mechanism can achieve. Predicts per-image reducibility. Strong correlation story across the seven Docker images.

- **CSV columns**: `acr_cve`, `acr_vc` (one per relevant target type — the merge applies to CVE today; will also apply to VC if/when VC merge is added)
- **Algorithm** (per `metric_proposals.md` M22):
  1. For each merge target type T_i, apply the merge key function k to all V_i nodes
  2. ACR(T_i) = |{k(v) : v ∈ V_i}| / |V_i|
- **Overlay**: ❌ none — no spatial location
- **Effort**: 1.5 hours — uses the existing CVE merge key from `cveMerge.ts`
- **Note**: implementable without depending on whether the merge is currently active — uses the key function regardless of UI state

---

### M24 — Column Purity (~1.5 hours, shared with sister plan)

**Why it matters**: confirms the typed schema renders faithfully. Drops below 1 only if the layout misplaces a node (which it shouldn't in dagre).

- **CSV column**: `column_purity`
- **Overlay**: ✅ — sister plan Phase 4 (halo for impure nodes)
- **Effort**: 1.5 hours total; CSV portion 30 min

---

### M25 — Type-Pair Crossing Decomposition (~2 hours, shared with sister plan)

**Why it matters**: pure-novelty metric exploiting the typed schema. Identifies which edge-type pairs concentrate the visual cost — could even auto-recommend the next reduction step.

- **CSV columns**: `crossings_top_pair_share`, `crossings_top_pair_label`
- **Overlay**: ✅ — sister plan Phase 2
- **Effort**: 2 hours total; CSV portion 30 min

---

### M26 — Edge-Type Distribution (~1 hour)

**Why it matters**: isolates the visual cost of `ENABLES` back-edges (the most disruptive edge type for layered drawings).

- **CSV columns**: per edge type, two columns — `etd_<type>` (count share) and `etl_<type>` (length-weighted share). For PAGDrawer with 9 edge types, that's 18 columns. Possibly overkill for the CSV — alternative: emit one wide string column `etd_breakdown` with format `"HAS_VULN:0.32 IS_INSTANCE_OF:0.28 ..."`
- **Recommend the wide-string approach** for CSV; expand into a real table only in the Statistics modal display
- **Overlay**: ❌ — already conveyed by edge color
- **Effort**: 1 hour — count + length-weight + CSV serialization

---

### M28 — Visual Clutter Score (~2 hours)

**Why it matters**: executive-summary single number. Useful for the abstract or summary table.

- **CSV column**: `clutter_score` (post-normalization composite)
- **Algorithm** (per the corrected `metric_proposals.md` M28): min-max normalize each component (edge density, C/E, EL-CV) across the image corpus, then average with equal weights. **Note**: requires knowing the min/max across the corpus, so this metric is **not computable per-snapshot**. It can only be computed once all snapshots are exported. Practical workflow:
  1. Export per-snapshot CSVs containing the raw components (edge density, C/E, EL-CV) without `clutter_score`
  2. Run a small post-processing step (in a notebook or a one-shot CLI script) that reads all CSVs, computes corpus min/max, normalizes, averages, and writes back the augmented CSV
- **Overlay**: ❌ — composite scalar
- **Effort**: 2 hours — components are already there (M2's `crossings_per_edge`, M5's `edge_length_cv`, the existing `drawing_area`); add edge-density column and the post-processing script
- **Implementation note**: the normalization requires the corpus to be defined. Document the convention: corpus = all images × all reduction steps that the user exports as part of the same run.

---

## Implementation Phases

Each phase ships independently. The body-of-paper metrics (Phase 1) should land before paper drafts go out for review.

### Phase 1 — Body of paper (~13 hours)

The five "if you can implement five" metrics from the prioritization:

- M1 Stress (~5 h) — incl. APSP
- M2 Crossing angle (~2 h)
- M14 Reachability preservation (~3 h) — incl. backend `?full=true` endpoint
- M20 Edge consolidation ratio (~3 h)
- M25 Type-pair crossings (~2 h, but shares some work with M2)

Wait — that's 15 h not 13. Re-checking: M2+M25 share `findCrossings` extension; do them together → ~3 h combined. M1+M11+M12 share APSP; doing M1 alone is ~5 h, plus 30 min of APSP-extraction prep that pays off in Phase 2.

Revised: ~13 h.

End state: the five most-important metrics are in the CSV. Paper draft can include them.

### Phase 2 — Appendix essentials (~7 hours)

- M19 Bridge contraction depth (~3 h, incl. backend) — also satisfies sister plan Phase 3
- M22 Attribute compression ratio (~1.5 h)
- M24 Column purity (~1.5 h) — also satisfies sister plan Phase 4
- M26 Edge-type distribution (~1 h)

End state: appendix table is fleshed out.

### Phase 3 — Topology preservation (~5 hours)

- M11 NP_k (~3.5 h) — APSP shared with M1
- M12 Trustworthiness (~1.5 h, after M11) — APSP and ranks shared

End state: the dimension-reduction-style story is complete.

### Phase 4 — Composite (~2 hours + post-processing)

- M28 Visual clutter (~2 h frontend + a small post-processing script)

End state: every recommended metric is in the CSV, and the corpus-normalized clutter score is computable post-hoc.

---

## Acceptance Criteria

- [ ] All 12 paper-priority metrics appear as CSV columns
- [ ] M1, M11, M12 share an APSP computation (computed once per snapshot, reused)
- [ ] M14 has a passing test on mock data showing rate = 1.0
- [ ] M19 backend `chain_length` covered by a unit test
- [ ] M20 returns `null` outside outcomes-mode merge
- [ ] M28 documented as "post-processing required for clutter_score"
- [ ] Each new metric has at least one unit test
- [ ] Frontend test count: 159 → ~200
- [ ] Backend test count: 381 → ~390 (M14 endpoint + M19 chain_length)
- [ ] CSV header order documented in `Docs/_domains/StatisticsModal.md` and `Docs/_domains/DrawingQualityMetrics.md`

---

## Risks and Open Questions

| # | Risk | Mitigation |
|---|------|------------|
| 1 | M1 APSP at ~830 nodes may be slow (~100–300 ms) | Lazy compute behind "Recompute" or "Export CSV" button; show spinner if > 300 ms |
| 2 | M14 needs the unreduced graph G; requires backend endpoint | Add `/api/graph/full` returning the canonical pre-reduction graph |
| 3 | M28 clutter_score needs corpus min/max — not per-snapshot | Document post-processing convention; provide example notebook |
| 4 | M26 with 9 edge types × 2 measures = 18 CSV columns | Use wide-string `etd_breakdown` column instead |
| 5 | M11/M12 require ranks of all nodes by both graph and layout distance — O(\|V\|² log \|V\|) | Acceptable at \|V\| ≤ 1000; cache between metrics |
| 6 | Backend `chain_length` recording at bridge-creation time may miss bridges added later (none currently — bridges only at visibility-toggle time) | Document that bridges are immutable once created in the current architecture |

---

## Out of Scope

Per `metric_proposals.md` § "How I would prioritise":

- **M6 Symmetry** — marginal for layered DAGs
- **M7 Edge Continuity** — Ware et al.'s favorite but doesn't connect tightly to PAGDrawer's three mechanisms
- **M29 Information Density** — formula too vague to be defensible

Visualization-only metrics (M3, M5, M8, M9, M21) belong to the sister plan, `Debug_Overlay_Visualizations.md`. They do not appear in this plan and are not paper-essential.

---

## Files Affected (Summary)

**Modified — frontend**:
- `frontend/js/features/metrics.ts` (+~400 LOC: 12 new computations, APSP helper, k-NN, ranks)
- `frontend/js/features/metrics.test.ts` (+~250 LOC)
- `frontend/js/ui/statistics.ts` (~50 LOC: surface new metrics in table)
- `frontend/js/services/api.ts` (+~10 LOC: `fetchFullGraph` for M14)

**Modified — backend (M14, M19)**:
- `src/viz/app.py` (+~30 LOC: `/api/graph/full` endpoint, M19 chain_length pass-through)
- `src/graph/builder.py` (+~10 LOC: record chain_length on bridge edges)
- `tests/test_builder.py` (+~30 LOC: M19 unit test)
- `tests/test_api_endpoints.py` (+~20 LOC: full-graph endpoint test)

**New (post-processing for M28)**:
- `scripts/compute_clutter_score.py` (~50 LOC: read CSVs, normalize, augment)

**Documentation updates after implementation**:
- `Docs/_domains/StatisticsModal.md` — list the new CSV columns
- `Docs/_domains/DrawingQualityMetrics.md` — formal definitions for the 12 new metrics
- `Docs/_dailyNotes/...-Paper_Metrics.md` — implementation log
