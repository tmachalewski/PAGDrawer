# Metric Visualizations and CSV Extension — Implementation Plan

**Created:** 2026-05-03-19-42
**Branch (proposed):** `feature/extended-metrics`
**Source plan:** `Docs/Plans/metric_proposals.md` (ratings ✅/⚠️/❌ per metric)

---

## Goal

Implement **all 10 ✅ Recommended metrics** from `metric_proposals.md` end-to-end:

1. Compute each metric in the browser (extending `frontend/js/features/metrics.ts`)
2. Add each as a column to the existing CSV export
3. Add each as a toggleable visual overlay on the graph

The 7 ⚠️ Possible metrics are **out of scope** for this plan; mention as future work.

---

## Decisions Locked In

| # | Choice | Why |
|---|--------|-----|
| 1 | Scope: 10 ✅ only (M2, M3, M5, M8, M9, M19, M20, M21, M24, M25). | Sticking to high-value, naturally-visualizable metrics. |
| 2 | All computation in the browser (`frontend/js/features/metrics.ts`); no Python batch script. | The Statistics modal already runs all reduction permutations through the browser; duplicating in Python is unnecessary work. |
| 3 | Each metric appears in **both** the CSV and the visual overlay. | Numbers for the paper, visuals for understanding. |
| 4 | Per-overlay checkboxes, moved to a **new "Debug Overlay" modal** reachable from the Statistics modal. | Keeps the Statistics modal clean (it's already wide); composable selection without conflicts. |
| 5 | Implementation order: M9 → M2 → M21 → M19 → M25 → M20 → M3 → M24 → M5 → M8. | Cheapest-first, biggest readability win first. |
| 6 | Backend changes only for M19 — expose bridge `chain_length` in `/api/graph` response. | Frontend reconstruction would be fragile. |

---

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────┐
│  metrics.ts (computation, no DOM)                        │
│   - DrawingMetrics interface                             │
│   - computeMetrics() returns scalar values               │
│   - findCrossings() returns per-crossing data            │
│   - NEW: per-edge / per-node / per-compound results     │
│     (returned alongside scalars for overlay rendering)   │
└──────────────┬───────────────────────────────────────────┘
               │
       ┌───────┴────────────────────┐
       │                            │
       ▼                            ▼
┌──────────────────┐    ┌────────────────────────────┐
│ statistics.ts    │    │ debugOverlay.ts (NEW)      │
│  - reads scalars │    │  - reads per-element data  │
│  - CSV export    │    │  - draws pseudo-elements    │
│  - opens debug   │    │  - 11 overlay toggles      │
│    modal button  │    │    (existing 4 + 10 new −  │
└──────────────────┘    │    3 conflicts)            │
                        └────────────────────────────┘
```

`metrics.ts` produces both **scalar metrics** (for CSV / Statistics modal table) and **per-element metric data** (for the overlay to render). The overlay code never recomputes — it reads cached `lastMetrics` data.

---

## Module Changes Overview

| File | Change |
|------|--------|
| `frontend/js/features/metrics.ts` | Add 10 computations; extend `DrawingMetrics` interface; extend `findCrossings` to return angle + type pair; add per-element data structures. |
| `frontend/js/features/metrics.test.ts` | Pure-function tests for all new computations. |
| `frontend/js/ui/statistics.ts` | Add the 10 new metrics to the Drawing Quality table; pass through to CSV; add a "🔍 Debug Overlay" button that opens the new modal. |
| `frontend/js/ui/debugOverlay.ts` | **NEW** — the modal logic, per-overlay checkbox state, and the rendering functions for each overlay (extracted from current `statistics.ts` debug code, plus 10 new ones). |
| `frontend/js/config/constants.ts` | New Cytoscape pseudo-element styles for overlay markers. |
| `frontend/index.html` | New `<div id="debug-overlay-modal">` with checkbox grid. |
| `frontend/css/styles.css` | Modal layout + overlay marker styles. |
| `frontend/js/main.ts` | Wire the new modal's open/close globals. |
| `src/viz/app.py` (backend) | M19 only — add `chain_length` to bridge edge response. |
| `src/graph/builder.py` (backend) | M19 only — record chain length when bridge edges are created. |
| `tests/test_builder.py` | M19 backend test. |

---

## Per-Metric Implementation Entries

Each entry: **scalar** (for CSV/table), **per-element data** (for overlay), **overlay rendering**, **conflicts**, **rough effort**.

---

### M9 — Aspect Ratio (~30 min)

- **Scalar**: `aspectRatio = min(w,h) / max(w,h)` from existing `computeBoundingBox`
- **Per-element**: none
- **Overlay**: extend the existing bbox label `Drawing area W × H` → `Drawing area W × H  (AR = 0.42)`
- **Conflicts**: none — uses the existing bbox element
- **CSV column**: `aspect_ratio`
- **Effort**: 30 min — single label change + CSV row + test

---

### M2 — Crossing Angle (~2 hours)

- **Scalar**: `meanCrossingAngle`, `minCrossingAngle`, `rightAngleRatio` (fraction within 15° of 90°)
- **Per-element**: extend `CrossingInfo` with `angle: number` (radians, in `[0, π/2]`)
- **Algorithm**: `angle = arctan2(|cross|, |dot|)` of edge direction vectors at the crossing
- **Overlay**: color the existing red dots by angle — red (acute, bad) → yellow (45°) → green (≈90°, good)
- **Conflicts**: with M25 (also colors crossing dots). Resolution: per-overlay checkbox group "Crossings color by:" with radio buttons (angle / type-pair / none)
- **CSV columns**: `crossings_mean_angle_deg`, `crossings_min_angle_deg`, `crossings_right_angle_ratio`
- **Effort**: 2 hours — angle math + per-dot color + 3 CSV columns + tests

---

### M21 — Group Cardinality, Generalized (~1 hour)

- **Scalar**: `largestGroupSize`, `singletonFraction` across all compound parents (any type)
- **Per-element**: `(parentId, memberCount)` tuples
- **Overlay**: ensure every compound parent label includes `(×N)`. Already done for `CVE_GROUP`; need to add for `COMPOUND` (Initial State) — but Initial State has 4 fixed children; the badge is informative anyway. Generalize the badge format so future compound types get it for free.
- **Conflicts**: none — adds to existing labels
- **CSV columns**: `compound_largest_group_size`, `compound_singleton_fraction`
- **Effort**: 1 hour — extract the label-formatting logic to a helper, add CSV, tests

---

### M19 — Bridge-Edge Contraction Depth (~3 hours)

- **Scalar**: `bridgeEdgeProportion = |bridges| / |edges|`, `meanContractionDepth = avg(chain_length over bridges)`
- **Per-element**: `(bridgeEdgeId, chainLength)` tuples
- **Backend change**:
  - `src/graph/builder.py` — when creating a bridge edge, record the contracted chain length on the edge data (e.g. `chain_length=3`)
  - `src/viz/app.py` — pass `chain_length` through in the API response edge data
- **Frontend**: read `chain_length` from edge data on rendered bridge edges; sum / count for scalars
- **Overlay**: small `k=N` label at the midpoint of each bridge edge
- **Conflicts**: none — bridges already have a distinct color
- **CSV columns**: `bridge_edge_proportion`, `mean_contraction_depth`
- **Effort**: 3 hours — backend wiring (1h) + frontend metric (30m) + label rendering (30m) + tests both sides (1h)
- **Risk**: bridge edges are only created when the user activates the visibility toggle on intermediate node types (CWE, TI). The metric is meaningful only when bridges exist; report `0` and `nan` (or `null` in CSV) otherwise.

---

### M25 — Type-Pair Crossing Decomposition (~2 hours)

- **Scalar**: top-3 type pairs by crossing count, e.g. `("HAS_VULN", "IS_INSTANCE_OF") → 18`, plus a single `crossings_top_pair_share` (fraction of all crossings concentrated in the most-crossing pair)
- **Per-element**: extend `CrossingInfo` with `edgeAType`, `edgeBType` (already partly there via `edgeA.sourceId/targetId` lookups; need to record the actual `data('type')` of the edge)
- **Overlay**: color the existing red dots by type pair (categorical palette, ≤9 distinct pairs in practice for PAGDrawer)
- **Conflicts**: with M2 (radio group, see M2)
- **CSV columns**: `crossings_top_pair_share`, `crossings_top_pair_label` (the pair name as a string)
- **Effort**: 2 hours — type recording in findCrossings + categorical palette + legend in modal + tests
- **Note**: avoid two CSV columns per type pair (would explode column count); the top-pair share is enough for a paper table.

---

### M20 — Edge Consolidation Ratio (~3 hours)

- **Scalar**: `meanEcrWeighted` (mean ECR weighted by group size)
- **Per-element**: `(parentId, ecr)` tuples
- **Algorithm**: for each compound parent — count raw incoming/outgoing edges (from `cy.nodes(parentId).children().connectedEdges()`) and synthetic incoming/outgoing edges (the existing `synthetic` flag from outcomes-mode merge); ECR = raw / synthetic per parent
- **Overlay**: append `ECR×N.M` to each compound parent's existing label, e.g. `AV:N / AC:L / PR:N / UI:N (×5)  ECR×3.4`
- **Conflicts**: with M21 (both modify compound labels). Resolution: a single "Compound annotations" overlay group with checkboxes for "Group size" (M21) and "ECR" (M20); when both on, label is `(×5  ECR×3.4)`
- **CSV columns**: `mean_ecr_weighted`
- **Effort**: 3 hours — ECR math (currently the merge module produces synthetic edges but doesn't remember the raw count; add a helper) + overlay label + tests
- **Risk**: only meaningful in outcomes-mode merge (the synthetic edges only exist there). In prereqs mode, ECR = 1 trivially. Report `null` outside outcomes mode.

---

### M3 — Angular Resolution at Nodes (~4 hours)

- **Scalar**: `minAngularResolutionDeg` (minimum across all nodes), `meanAngularResolutionNormalized` (each node's smallest gap divided by ideal `2π/k`, averaged)
- **Per-element**: `(nodeId, smallestGapAngle, ideal)` tuples for the worst N nodes
- **Algorithm**: for each visible node with ≥ 2 incident edges, compute incidence angles via `arctan2`, sort, take cyclic differences, find min
- **Overlay**: small arc inside the narrowest gap at each "bad" node (gap < 60% of ideal). Color by goodness — red (very narrow) to yellow (60% threshold)
- **Conflicts**: none (new visual element type)
- **CSV columns**: `min_angular_resolution_deg`, `mean_angular_resolution_normalized`
- **Effort**: 4 hours — math (1h) + arc rendering as new pseudo-elements (`type="ANG_RES_DEBUG"`) (1.5h) + tests (1.5h)

---

### M24 — Column Purity (~1.5 hours)

- **Scalar**: `columnPurity` (fraction of nodes whose layout column matches their type's expected column)
- **Per-element**: list of impure node IDs
- **Algorithm**: type → expected column index already in `getColumnPositions()` in `layout.ts`. For each visible node, compute its layout column from `n.position('x')` and dagre's column boundaries (or read directly from dagre output if exposed). Compare to expected
- **Overlay**: draw a halo (large semi-transparent ring) around impure nodes
- **Conflicts**: none
- **CSV columns**: `column_purity`
- **Effort**: 1.5 hours — column-from-position math (probably needs dagre internals or a heuristic with column tolerance) + halo rendering + tests
- **Risk**: dagre doesn't expose column indices directly; we may need to bucket x-positions by clustering or by using `getColumnPositions()` rank values. Plan for a tolerance check (within ±10% of expected x-center).

---

### M5 — Edge Length Per-Edge Tinting (~2 hours)

- **Scalar**: already exported (`edge_length_cv`); no new scalar
- **Per-element**: `(edgeId, deviationFromMean)` tuples
- **Overlay**: tint each edge by deviation from the mean — cool color (blue) for shorter than mean, warm color (red) for longer. Saturation proportional to magnitude. Existing edge-type colors are replaced for the duration of this overlay
- **Conflicts**: with the entire edge-color scheme. Resolution: this overlay swaps the edge color stylesheet temporarily; only one "edge tint" overlay can be active at a time. Add a radio group "Edge tint:" with options (none / by-length-deviation / future M4)
- **CSV columns**: none new (covered by `edge_length_cv`)
- **Effort**: 2 hours — color mapping (1h) + style swap mechanism (1h) — easier said than done because Cytoscape stylesheets need to be reloaded; might need dynamic per-element style overrides
- **Defer if hard**: this is the most complex visualization to plumb, with the smallest payoff. If implementation gets messy, ship without M5 in this batch.

---

### M8 — Bbox Compactness Shading (~2 hours)

- **Scalar**: `compactness = inkArea / bboxArea` where `inkArea = Σ_v π·r² + Σ_e ‖e‖·strokeWidth`
- **Per-element**: none
- **Overlay**: fill the existing blue bbox with a shading proportional to compactness — denser fill = higher compactness. Visualization is a single filled rectangle behind the graph
- **Conflicts**: none
- **CSV column**: `compactness`
- **Effort**: 2 hours — node area + edge area math (1h) + bbox fill (already a node, just change `background-opacity`) + tests
- **Note**: the shading is a single global fill, not per-region. That's the right granularity — readers don't want a heatmap of where ink lives.

---

## New Debug Overlay Modal

### Layout

```
┌───────────────────────────────────────────────────┐
│ 🔍 Debug Overlay Settings              [×]      │
├───────────────────────────────────────────────────┤
│                                                   │
│ Existing overlays:                                │
│   ☑ Edge crossings (red dots)                    │
│   ☑ Drawing area (blue rectangle)                │
│   ☑ Mean edge length (green line)                │
│   ☑ Std-dev (orange line)                        │
│                                                   │
│ Crossings — color by:                            │
│   ◯ none (default red)                           │
│   ◯ angle (M2)                                    │
│   ◯ type pair (M25)        [legend ▾]            │
│                                                   │
│ Compound annotations:                             │
│   ☑ Group size ×N (M21)                          │
│   ☐ ECR×N.M (M20)                                │
│                                                   │
│ Per-element diagnostics:                         │
│   ☐ Bridge contraction depth labels (M19)        │
│   ☐ Angular resolution arcs (M3)                 │
│   ☐ Column purity halos (M24)                    │
│                                                   │
│ Whole-graph annotations:                         │
│   ☐ Aspect ratio in bbox label (M9)              │
│   ☐ Compactness fill in bbox (M8)                │
│                                                   │
│ Edge tint:                                        │
│   ◯ none (default colors by edge type)           │
│   ◯ length deviation (M5)                        │
│                                                   │
│      [ Apply ]   [ Reset to defaults ]            │
└───────────────────────────────────────────────────┘
```

### Reach

The Statistics modal's existing **🔍 Show debug overlay** button changes:
- **Single click** still toggles overlays on/off with last-used settings (default: existing 4 overlays only)
- **Right click** (or a small ⚙️ next to it) opens this **Debug Overlay Settings** modal

The button label reflects which overlays are currently active, e.g. `🔍 Debug overlays (3 active)`.

### State persistence

Overlay selection persists in `localStorage` per browser. No backend involvement.

---

## Implementation Phases

Each phase ships independently to `feature/extended-metrics`, then the whole branch merges to `main` at the end (or after each phase if intermediate merges are preferred).

### Phase 1 — Quick wins (~3 hours)

- M9 (aspect ratio label)
- M21 (generalized group cardinality badges)
- New Debug Overlay modal scaffold + checkbox state machine + per-overlay toggle of existing 4 overlays

End state: every existing overlay individually toggleable; AR shown in bbox label; group-size badge consistent across compound types.

### Phase 2 — Crossings refinement (~4 hours)

- M2 (crossing angle math + dot coloring)
- M25 (type-pair crossing decomposition + dot coloring)
- Radio-group UI for "Crossings color by"

End state: crossings tell two new stories (angle quality, type-pair concentration).

### Phase 3 — Bridges and merges (~6 hours)

- Backend M19 (chain_length plumbing)
- M19 frontend (label rendering + scalars)
- M20 (ECR computation + label addition)

End state: the two reduction mechanisms (bridges, merges) are visually quantified.

### Phase 4 — Layout diagnostics (~5.5 hours)

- M3 (angular resolution arcs)
- M24 (column purity halos)

End state: layout problems pop visually.

### Phase 5 — Surface treatments (~4 hours)

- M5 (edge length deviation tint) — defer if hard
- M8 (compactness shading)

End state: visual richness for paper figures.

**Total: ~22 hours of focused work.**

---

## Acceptance Criteria

- [ ] All 10 ✅ metrics appear as columns in the Drawing Quality CSV export
- [ ] All 10 ✅ metrics have a corresponding visual overlay
- [ ] Debug Overlay Settings modal exposes per-overlay toggles
- [ ] Modal state persists across page reload (localStorage)
- [ ] Existing 4 overlays still work and are individually toggleable
- [ ] No new overlay can be applied to a hidden / exploit-hidden element
- [ ] Toggling any overlay does not change the computed metric values
- [ ] Backend `chain_length` exposed for bridge edges
- [ ] Backend `chain_length` covered by a unit test
- [ ] Each new metric has at least one unit test in `metrics.test.ts`
- [ ] Frontend test count passes (current: 159 → expected: ~190)
- [ ] All metrics handle empty / single-node / no-bridges / no-compounds gracefully (no NaN, no crashes)
- [ ] CSV header order documented in `Docs/_domains/StatisticsModal.md` and `Docs/_domains/DrawingQualityMetrics.md`

---

## Risks and Open Questions

| # | Risk | Mitigation |
|---|------|------------|
| 1 | Cytoscape stylesheet swap for M5 (per-edge tint) is more complex than per-element data attributes | If `cy.style()` overrides per-edge prove fragile, defer M5 to a later phase or skip in this batch |
| 2 | Dagre column index not directly exposed; M24 needs a heuristic | Use `getColumnPositions()` rank values and a tolerance match on x-position; document the tolerance |
| 3 | M20 (ECR) only meaningful in outcomes merge | Document `null` value outside outcomes mode in CSV and modal |
| 4 | M19 needs backend cooperation; bridge edges only created on visibility toggle | Document that the metric is `0` when no bridges exist |
| 5 | Modal grows beyond ~12 toggles → cognitive load | Group toggles into 5 sections (existing, crossings, compound annotations, per-element, surface treatments) |
| 6 | Overlay rendering performance on large graphs (e.g. nginx, 830 nodes, hundreds of crossings) | Each overlay creates pseudo-elements; profile after Phase 2; if slow, batch additions and consider rendering as a single SVG layer instead of per-element pseudo-nodes |
| 7 | localStorage state may carry stale overlay names after a future renaming | Version the localStorage schema (`debugOverlayState_v1`) and reset on version mismatch |
| 8 | CSV column count grows from 10 → ~22 | Keep ordering consistent; document in domain doc; no other consumers depend on column order |

---

## Out of Scope (Deferred)

The 7 ⚠️ Possible metrics from `metric_proposals.md` — listed for reference, not implemented in this plan:

| Metric | Reason deferred |
|--------|----------------|
| M1 Stress | O(\|V\|·(\|V\|+\|E\|)) APSP; expensive for live computation; better fit for offline analysis |
| M4 Edge orthogonality | Same edge-color conflict as M5, less paper value |
| M7 Edge continuity | Per-2-path computation; visually busy; less aligned with the three reduction mechanisms |
| M11 NP_k | Requires per-node click interaction; bigger UX design |
| M12 Trustworthiness | Same |
| M13 Gabriel graph overlay | Visually dense; primarily an academic curiosity for PAGDrawer |
| M27 Layer balance | Better as a sidebar histogram than a graph overlay |

A future plan can pick up any of these if the paper requires them.

---

## Files Affected (Summary)

**New files**:
- `frontend/js/ui/debugOverlay.ts` (~350 LOC)
- `frontend/js/ui/debugOverlay.test.ts` (~100 LOC)

**Modified — major**:
- `frontend/js/features/metrics.ts` (+~250 LOC: 10 new computations + per-element data structures)
- `frontend/js/features/metrics.test.ts` (+~150 LOC: tests for each new computation)
- `frontend/js/ui/statistics.ts` (~50 LOC: surface new metrics in table; "Debug Overlay" button → modal)
- `frontend/js/config/constants.ts` (~80 LOC: new pseudo-element styles for M3, M24, M19, etc.)
- `frontend/index.html` (+~80 LOC: modal markup)
- `frontend/css/styles.css` (+~120 LOC: modal layout, overlay markers, theme variants)
- `frontend/js/main.ts` (+~5 LOC: wire modal globals)

**Modified — minor (M19 backend)**:
- `src/graph/builder.py` (~10 LOC: record chain length on bridge edges)
- `src/viz/app.py` (~5 LOC: pass through to API)
- `tests/test_builder.py` (+~30 LOC: M19 backend test)

**Documentation updates after implementation**:
- `Docs/_domains/StatisticsModal.md` — describe the new Debug Overlay modal
- `Docs/_domains/DrawingQualityMetrics.md` — list all new metrics with formulas
- `Docs/_dailyNotes/...-Extended_Metrics.md` — implementation log
