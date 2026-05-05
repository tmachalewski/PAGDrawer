# Paper Evaluation Metrics — Implementation Plan

**Created:** 2026-05-03-19-42
**Branches (proposed):** stage sub-branches under the umbrella `feature/metrics-roadmap` — Paper-plan work spans `feature/metrics-roadmap-stress`, `.../bridges-and-merges`, `.../paper-appendix`, `.../layout-diagnostics`, `.../topology-preservation`. See Master roadmap for the full sequencing.
**Source plan:** `Docs/Plans/metric_proposals.md` § "How I would prioritise"
**Sister plans:**
- `Docs/Plans/Debug_Overlay_Visualizations.md` — visualization-priority ordering
- `Docs/Plans/JSON_Export_With_Settings.md` — orthogonal export-format work

> ⚠️ **Scope axis: paper importance, not visualization.** This plan picks the metrics the GD 2026 reviewers will look for in your evaluation table — regardless of whether they have a natural overlay. Metrics that visualize well but aren't in the recommended evaluation set live in the sister plan.

---

## Goal

Implement **10 metrics** from the recommendation set in `metric_proposals.md` § "How I would prioritise":

- **Body-of-paper** (the "if you can implement five" tier, **minus M14 deferred**): M1, M2, M20, M25
- **Appendix-only**: M11, M12, M19, M22, M24, M26

Every metric ends up as a CSV column. Visualizations are added only where they overlap with the sister plan; otherwise the metric is **export-only** and inspected as a number in the Statistics modal.

---

## Deferred for now

These are listed in `metric_proposals.md` § "How I would prioritise" but explicitly out of scope for this iteration:

| Metric | Reason for deferral |
|---|---|
| **M14 Reachability preservation rate** | Requires settling "what is G?" (the unreduced reference graph) and a backend `/api/graph/full` endpoint. Worth it for the paper, but a separate sub-plan. |
| **M28 Visual clutter** | Requires corpus-level normalization, which forces a post-processing step that fragments the workflow. Defer to a follow-up plan if reviewers flag the gap. |

These should be revisited after Phase 3 lands. Excluded from the start per `metric_proposals.md` § "would NOT pursue": **M6 Symmetry, M7 Edge Continuity, M29 Information Density**.

---

## Decisions Locked In

| # | Choice | Why |
|---|--------|-----|
| 1 | Scope: 10 metrics — M1, M2, M11, M12, M19, M20, M22, M24, M25, M26. | Mirrors the paper-importance prioritization in `metric_proposals.md`, minus M14 and M28 (deferred). |
| 2 | All computation in the browser (`frontend/js/features/metrics.ts`). | Same rationale as the sister plan; metrics modal already runs in the browser. |
| 3 | Every metric appears in the CSV. Visualizations only where the sister plan covers them. | The paper consumes CSV; overlays are bonus, not a requirement. |
| 4 | M11 and M12 (k-NN preservation, trustworthiness) are export-only — no per-node interactive overlay in this plan. | Per-node overlays require interaction work that's deferred to a future plan. |
| 5 | Implementation order: body metrics first (M1 → M2 → M20 → M25), then appendix metrics (M19 → M24 → M26 → M22 → M11 → M12). | Body metrics unblock the paper; appendix metrics polish it. |
| 6 | Backend changes only for M19 (chain_length). | Minimize backend churn. |
| 7 | M1 Stress uses BFS-based APSP for unweighted graphs (matches PAGDrawer's edge model). | Dijkstra unnecessary; BFS is simpler and faster. |
| 8 | M26 emits **one CSV column per edge type** (`edge_type_HAS_VULN`, `edge_type_IS_INSTANCE_OF`, ...). JSON export emits a single nested object. | The edge-type enum is fixed in the codebase; flat columns parse everywhere (Excel included), keep the CSV header self-describing, and avoid the escaped-string pitfalls of in-cell JSON. |

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

If both plans run, these five are implemented once. If only this plan runs, the sister-plan visualization for these five is dropped (export-only here).

Metrics **unique to this plan** (no overlay needed; export-only):

- M1 Stress
- M11 Neighborhood preservation (k-NN overlap)
- M12 Trustworthiness & continuity
- M22 Attribute compression ratio
- M26 Edge-type distribution

---

## Per-Metric Implementation Entries

Each entry: scalar(s) for CSV / Statistics modal, algorithm, overlay status, risks.

---

### M1 — Stress

**Why it matters**: the most-cited GD layout-quality metric. Reviewers expect it.

- **CSV columns**: `stress_per_pair`, `stress_unreachable_pairs`
- **Algorithm**:
  1. Compute APSP on the visible graph via BFS from each node — O(|V|·(|V|+|E|))
  2. Treat the graph as undirected for distance computation (matches Purchase 2002)
  3. For each reachable pair (i, j), compute `(‖p_i − p_j‖_logical − d_ij)²`
  4. Sum, divide by the count of reachable pairs (skip unreachable, report the count separately as `stress_unreachable_pairs`)
- **Disconnected-graph convention**: skip-and-report (per `metric_proposals.md` Implementation Notes)
- **Overlay**: ❌ none in this plan (sister plan has it as ⚠️ — defer)
- **Tests**: known-layout sanity checks; trivial-graph edge cases (1 node, 2 nodes)
- **Risk**: APSP cost on the largest scans. Mitigation: lazy compute (only on Statistics modal open or CSV export click). The same APSP feeds M11 and M12 — compute once and cache.

---

### M2 — Crossing Angle (shared with sister plan)

**Why it matters**: Huang et al. (2014) — "larger crossing angles make graphs easier to read". Path-tracing performance directly correlates with crossing angle.

- **CSV columns**: `crossings_mean_angle_deg`, `crossings_min_angle_deg`, `crossings_right_angle_ratio`
- **Algorithm**: extend `findCrossings()` so each `CrossingInfo` carries `angle: number` (radians). Compute via `arctan2(|cross|, |dot|)` of edge direction vectors at the crossing point.
- **Overlay**: ✅ — see sister plan Phase 2. Skip if sister plan does not run.
- **Tests**: K4-in-a-square has crossing at exactly 90°; mean of two perpendicular crossings = 90°

---

### M11 — Neighborhood Preservation (k-NN Overlap)

**Why it matters**: quantifies whether your reductions trade neighborhood faithfulness for compactness — directly relevant to compound merging.

- **CSV columns**: `np_k5`, `np_k10`, `np_k20` (three values of k)
- **Algorithm** (per `metric_proposals.md` M11):
  1. Reuse APSP from M1 — no extra cost
  2. For each node v: top-k graph neighbors `N_k^G(v)` (k smallest finite `D[v][·]`); top-k layout neighbors `N_k^L(v)` (k smallest Euclidean from `pos[v]`)
  3. NP_k(v) = |N_k^G(v) ∩ N_k^L(v)| / k
  4. Average across nodes with ≥ k reachable neighbors; report `np_k_excluded` count
- **Overlay**: ❌ none (per-node, on-click overlay deferred to a future "interactive diagnostics" plan)
- **Risk**: requires M1's APSP to ship first (or compute it together)

---

### M12 — Trustworthiness and Continuity

**Why it matters**: decomposes M11's error into "false friends" and "missing friends" — diagnoses *what kind* of neighborhood violation the merge mechanism causes.

- **CSV columns**: `trust_k10`, `cont_k10` (single k = 10 to keep CSV manageable)
- **Algorithm** (per `metric_proposals.md` M12): same APSP + layout-distance setup as M11, but with rank-weighted asymmetric sums. Use Venna & Kaski 2001's formula.
- **Overlay**: ❌ none
- **Risk**: requires M11's ranks to ship first (or compute together)

---

### M19 — Bridge-Edge Proportion and Contraction Depth (shared with sister plan)

**Why it matters**: tells the reader whether your "bridge edges" represent one collapsed node or chains of five — transparency about how synthetic the reduced graph is.

- **CSV columns**: `bridge_edge_proportion`, `mean_contraction_depth`
- **Backend change**: `chain_length` recorded on each bridge edge in `src/graph/builder.py`, exposed in API response by `src/viz/app.py`
- **Overlay**: ✅ — sister plan Phase 3
- **Risk**: only meaningful when bridges exist (when CWE/TI visibility toggles are active). Emit `0` and `null` when not.

---

### M20 — Edge Consolidation Ratio (shared with sister plan)

**Why it matters**: per-group compression factor for the merge mechanism — tells the reader whether the merge is concentrated in a few large groups or distributed.

- **CSV column**: `mean_ecr_weighted` (size-weighted mean across all compound parents)
- **Overlay**: ✅ — sister plan Phase 3
- **Algorithm**: count raw incoming/outgoing edges from each compound parent's children versus the synthetic post-consolidation edges
- **Risk**: only meaningful in outcomes-mode merge — emit `null` outside outcomes mode

---

### M22 — Attribute Compression Ratio

**Why it matters**: the structural upper bound on what the merge mechanism can achieve. Predicts per-image reducibility.

- **CSV columns**: `acr_cve` (one per relevant target type — currently CVE; extend later if VC merge ships)
- **Algorithm** (per `metric_proposals.md` M22):
  1. For each merge target type T_i, apply the merge key function k to all V_i nodes
  2. ACR(T_i) = |{k(v) : v ∈ V_i}| / |V_i|
- **Overlay**: ❌ none — no spatial location
- **Implementation note**: requires the merge key functions (`computePrereqKey` / `computeOutcomeKey`) extracted from `cveMerge.ts` into a shared `mergeKeys.ts` module that both `cveMerge.ts` and `metrics.ts` can import.

---

### M24 — Column Purity (shared with sister plan)

**Why it matters**: confirms the typed schema renders faithfully. Drops below 1 only if the layout misplaces a node.

- **CSV column**: `column_purity`
- **Overlay**: ✅ — sister plan Phase 4 (halo for impure nodes)
- **Risk**: dagre doesn't expose column indices directly; need a heuristic with x-position tolerance. Plan for ±10% of expected column-center.

---

### M25 — Type-Pair Crossing Decomposition (shared with sister plan)

**Why it matters**: pure-novelty metric exploiting the typed schema. Identifies which edge-type pairs concentrate the visual cost.

- **CSV columns**: `crossings_top_pair_share`, `crossings_top_pair_label`
- **Overlay**: ✅ — sister plan Phase 2
- **Algorithm**: extend `findCrossings()` to record edge type of each crossing pair; compute frequencies; report top pair

---

### M26 — Edge-Type Distribution

**Why it matters**: isolates the visual cost of `ENABLES` back-edges (the most disruptive edge type for layered drawings).

- **CSV columns**: one column per edge type — `edge_type_HAS_VULN`, `edge_type_IS_INSTANCE_OF`, `edge_type_LEADS_TO`, `edge_type_ENABLES`, etc. Each cell is a numeric share in `[0, 1]`. The column set is fixed by the edge-type enum in the codebase; absent edge types emit `0`.
- **JSON export**: real nested object under `metrics.edge_type_distribution`, e.g. `{"HAS_VULN":0.36,"IS_INSTANCE_OF":0.18,...}` (no escaping; `0` for absent types).
- **Overlay**: ❌ — already conveyed by edge color
- **Implementation note**: emit per-edge-type **count share** by default. The length-weighted variant is interesting but doubles the column footprint; defer unless paper reviewers ask. The fixed column list keeps CSV diffs across exports stable.

---

## Implementation Phases

Each phase ships independently. The body-of-paper metrics (Phase 1) should land before paper drafts go out for review.

### Phase 1 — Body of paper

The body metrics (now 4 because M14 is deferred):

- M1 Stress (incl. APSP helper that M11 / M12 will reuse later)
- M2 Crossing angle (extends `findCrossings`)
- M20 Edge consolidation ratio
- M25 Type-pair crossings (also extends `findCrossings`; do alongside M2)

End state: the four body metrics are in the CSV. Paper draft can include them.

### Phase 2 — Appendix essentials

- M19 Bridge contraction depth (incl. backend `chain_length` wiring)
- M22 Attribute compression ratio (incl. extracting `mergeKeys.ts` from `cveMerge.ts`)
- M24 Column purity
- M26 Edge-type distribution (one CSV column per edge type)

End state: appendix table is fleshed out.

### Phase 3 — Topology preservation

- M11 NP_k (reuses APSP from M1)
- M12 Trustworthiness (reuses APSP and ranks from M11)

End state: the dimension-reduction-style story is complete in CSV.

---

## Acceptance Criteria

- [ ] All 10 paper-priority metrics appear as CSV columns
- [ ] M1, M11, M12 share an APSP computation (computed once per snapshot, reused)
- [ ] M19 backend `chain_length` covered by a unit test
- [ ] M20 returns `null` outside outcomes-mode merge
- [ ] M22 uses an extracted `mergeKeys.ts` module — no duplication of key logic
- [ ] M26 emits one CSV column per edge type with column names matching the edge-type enum; JSON export emits a single nested `edge_type_distribution` object
- [ ] Each new metric has at least one unit test
- [ ] CSV header order documented in `Docs/_domains/StatisticsModal.md` and `Docs/_domains/DrawingQualityMetrics.md`

---

## Risks and Open Questions

| # | Risk | Mitigation |
|---|------|------------|
| 1 | M1 APSP at large scans may be slow | Lazy compute behind "Recompute" or "Export CSV" click; show spinner on long runs |
| 2 | M11/M12 require ranks of all nodes by both graph and layout distance | Cache between metrics; share with M1's APSP |
| 3 | M19 backend `chain_length` recording at bridge-creation time may miss bridges added later | Bridges are immutable in current architecture; document and unit-test the create path |
| 4 | M22 needs merge keys extracted from `cveMerge.ts` | Plan an explicit `mergeKeys.ts` extraction step at the top of Phase 2 |
| 5 | M26 column set must stay in sync with the edge-type enum — adding a new edge type silently widens the CSV header | Sourced from the same enum that produces edge styles; a single source-of-truth constant ensures additions propagate to both. Add a regression test asserting CSV column names == enum values. |

---

## Files Affected (Summary)

**Modified — frontend**:
- `frontend/js/features/metrics.ts` — 10 new computations, APSP helper, k-NN, ranks
- `frontend/js/features/metrics.test.ts`
- `frontend/js/ui/statistics.ts` — surface new metrics in table

**New — frontend**:
- `frontend/js/features/mergeKeys.ts` — extracted from `cveMerge.ts` for M22 reuse

**Modified — backend (M19 only)**:
- `src/viz/app.py` — pass `chain_length` through in API response
- `src/graph/builder.py` — record `chain_length` on bridge edges
- `tests/test_builder.py` — M19 unit test

**Documentation updates after implementation**:
- `Docs/_domains/StatisticsModal.md` — list the new CSV columns including the per-edge-type M26 columns
- `Docs/_domains/DrawingQualityMetrics.md` — formal definitions for the 10 new metrics
- `Docs/_dailyNotes/...-Paper_Metrics.md` — implementation log
