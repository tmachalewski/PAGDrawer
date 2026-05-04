# Debug Overlay Visualizations — Implementation Plan

**Created:** 2026-05-03-19-42
**Branches (proposed):** stage sub-branches under the umbrella `feature/metrics-roadmap` — overlay work spans `feature/metrics-roadmap-overlay-foundation`, `.../crossings`, `.../bridges-and-merges`, `.../layout-diagnostics`, plus the post-umbrella `feature/visualization-surface` for Stage 8. See Master roadmap for the full sequencing.
**Source plan:** `Docs/Plans/metric_proposals.md` (ratings ✅/⚠️/❌ per metric)
**Sister plans:**
- `Docs/Plans/Paper_Evaluation_Metrics.md` — paper-importance ordering (the "what reviewers want to see" set)
- `Docs/Plans/JSON_Export_With_Settings.md` — orthogonal export-format work (CSV stays; JSON adds a settings-snapshot variant)

> ⚠️ **Scope axis: visualization, not paper importance.** This plan picks metrics that can be **drawn naturally on the graph**. It is not the right plan for "what should appear in the paper's evaluation table" — that's `Paper_Evaluation_Metrics.md`. The two plans overlap on M2, M19, M20, M24, M25 (work done either place satisfies both); they differ on the rest.

---

## Goal

Implement **all 10 metrics rated ✅ for debug-overlay viability** in `metric_proposals.md` end-to-end:

1. Compute each metric in the browser (extending `frontend/js/features/metrics.ts`)
2. Add each as a column to the existing CSV export
3. Add each as a toggleable visual overlay on the graph

The 10 metrics: **M2, M3, M5, M8, M9, M19, M20, M21, M24, M25**.

The 7 ⚠️ Possible-overlay metrics are out of scope for this plan; mention as future work.

> Several visualization-friendly metrics in this plan (M3, M5, M8, M9, M21) are **not** part of the paper's recommended evaluation set. They are included here because they're cheap and add value to the live debug experience, not because the paper needs them.

---

## Decisions Locked In

| # | Choice | Why |
|---|--------|-----|
| 1 | Scope: 10 ✅-overlay-viable (M2, M3, M5, M8, M9, M19, M20, M21, M24, M25). | These are the metrics that *visualize naturally*. |
| 2 | All computation in the browser (`frontend/js/features/metrics.ts`); no Python batch script. | The Statistics modal already runs through the browser; duplicating in Python is unnecessary work. |
| 3 | Each metric appears in **both** the CSV and the visual overlay. | Numbers for inspection, visuals for understanding. |
| 4 | Per-overlay checkboxes, moved to a **new "Debug Overlay" modal** reachable from the Statistics modal. | Keeps the Statistics modal clean (it's already wide); composable selection without conflicts. |
| 5 | Implementation order: M9 → M2 → M21 → M19 → M25 → M20 → M3 → M24 → M5 → M8. | Cheapest-first, biggest readability win first. |
| 6 | Backend changes only for M19 — expose bridge `chain_length` in `/api/graph` response. | Frontend reconstruction would be fragile. |
| 7 | Existing 4 overlays are **extracted** into the new `debugOverlay.ts` module before any new overlay work begins. | Avoids two homes for overlay logic. See "Existing-overlay extraction" below for the detailed plan. |
| 8 | The modal exposes **named presets** (Crossings analysis / Layout diagnostics / Reduction transparency / Defaults / Clear all) in addition to per-overlay toggles. | One-click sensible configurations; users tweak after if they want. |

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
│  - opens debug   │    │  - per-overlay toggles +   │
│    modal button  │    │    presets                  │
└──────────────────┘    └────────────────────────────┘
```

`metrics.ts` produces both **scalar metrics** (for CSV / Statistics modal table) and **per-element metric data** (for the overlay to render). The overlay code never recomputes — it reads cached `lastMetrics` data.

---

## Existing-Overlay Extraction (the prerequisite)

The four existing overlays (red crossing dots, blue bbox, green mean-edge line, orange std-dev line) currently live as private functions inside `frontend/js/ui/statistics.ts`:

- `drawDebugOverlay()` — orchestrates all four
- `clearDebugOverlay()` — removes all four
- `addUnitEdge()` — helper for the green and orange lines
- Plus shared state in `debugElementIds: string[]` and `wireCrossingsToggle()` button-state code

This needs to move out before any new overlays land, otherwise the new code has no obvious home and the modal's per-overlay toggle logic gets tangled with the all-or-nothing existing toggle.

### Extraction steps (in order)

1. **Create `frontend/js/ui/debugOverlay.ts`** with the same exports/behavior signatures the existing call sites already use:
   - `showDebugOverlay()` — formerly `drawDebugOverlay()`
   - `hideDebugOverlay()` — formerly `clearDebugOverlay()`
   - `isDebugOverlayActive(): boolean` — reads internal state
2. Move `debugElementIds`, `addUnitEdge`, the four overlay-drawing functions, and the Cytoscape style constants (already in `constants.ts`, no change there) into the new module.
3. **Replace** the inline functions in `statistics.ts` with imports + re-export of `wireCrossingsToggle()` so the existing button keeps working.
4. **Verify** existing tests pass without modification — the public API is unchanged at this point.
5. **Then** generalise the internal data model from "all four overlays toggle together" to "each overlay is a named entry in a state object":
   ```typescript
   interface OverlayState {
     crossings:     boolean;
     drawingArea:   boolean;
     meanEdgeLine:  boolean;
     stdDevLine:    boolean;
     // new toggles added in subsequent phases
   }
   ```
   Update `showDebugOverlay()` to read from this state object and call only the enabled drawing functions.
6. **Add per-overlay public toggles**:
   - `setOverlayState(state: Partial<OverlayState>): void`
   - `getOverlayState(): OverlayState`
   - `applyPreset(name: PresetName): void`
7. **Add localStorage persistence**: keyed `debugOverlayState_v1`. Load on module init; save on every `setOverlayState` / `applyPreset` call. Version-suffixed key so future schema changes can reset cleanly.

End state: existing four overlays still work identically from the user's perspective; their logic lives in the new module; per-overlay state machine is in place; subsequent phases just add new entries to `OverlayState` and new drawing functions.

This extraction is the **first task** of Phase 1 — every subsequent phase builds on it.

---

## Module Changes Overview

| File | Change |
|------|--------|
| `frontend/js/features/metrics.ts` | Add 10 computations; extend `DrawingMetrics` interface; extend `findCrossings` to return angle + type pair; add per-element data structures. |
| `frontend/js/features/metrics.test.ts` | Pure-function tests for all new computations. |
| `frontend/js/ui/statistics.ts` | Add the 10 new metrics to the Drawing Quality table; pass through to CSV; replace inline overlay code with imports from the new module; add a "🔍 Debug Overlay" button that opens the new modal. |
| `frontend/js/ui/debugOverlay.ts` | **NEW** — extracted overlay drawing logic + per-overlay state machine + presets + localStorage persistence + the new modal's open/close/event-handling. |
| `frontend/js/ui/debugOverlay.test.ts` | **NEW** — state-machine tests, preset application tests. |
| `frontend/js/config/constants.ts` | New Cytoscape pseudo-element styles for overlay markers. |
| `frontend/index.html` | New `<div id="debug-overlay-modal">` with checkbox grid + preset buttons. |
| `frontend/css/styles.css` | Modal layout + overlay marker styles. |
| `frontend/js/main.ts` | Wire the new modal's open/close globals. |
| `src/viz/app.py` (backend) | M19 only — add `chain_length` to bridge edge response. |
| `src/graph/builder.py` (backend) | M19 only — record chain length when bridge edges are created. |
| `tests/test_builder.py` | M19 backend test. |

---

## Per-Metric Implementation Entries

Each entry: **scalar** (for CSV/table), **per-element data** (for overlay), **overlay rendering**, **conflicts**.

---

### M9 — Aspect Ratio

- **Scalar**: `aspectRatio = min(w,h) / max(w,h)` from existing `computeBoundingBox`
- **Per-element**: none
- **Overlay**: extend the existing bbox label `Drawing area W × H` → `Drawing area W × H  (AR = 0.42)`
- **Conflicts**: none — uses the existing bbox element
- **CSV column**: `aspect_ratio`

---

### M2 — Crossing Angle

- **Scalar**: `meanCrossingAngle`, `minCrossingAngle`, `rightAngleRatio` (fraction within 15° of 90°)
- **Per-element**: extend `CrossingInfo` with `angle: number` (radians, in `[0, π/2]`)
- **Algorithm**: `angle = arctan2(|cross|, |dot|)` of edge direction vectors at the crossing
- **Overlay**: color the existing red dots by angle — red (acute, bad) → yellow (45°) → green (≈90°, good)
- **Conflicts**: with M25 (also colors crossing dots). Resolution: per-overlay checkbox group "Crossings color by:" with radio buttons (angle / type-pair / none)
- **CSV columns**: `crossings_mean_angle_deg`, `crossings_min_angle_deg`, `crossings_right_angle_ratio`

---

### M21 — Group Cardinality, Generalized

- **Scalar**: `largestGroupSize`, `singletonFraction` across all compound parents (any type)
- **Per-element**: `(parentId, memberCount)` tuples
- **Overlay**: ensure every compound parent label includes `(×N)`. Already done for `CVE_GROUP`; need to add for `COMPOUND` (Initial State). Generalize the badge format so future compound types get it for free.
- **Conflicts**: none — adds to existing labels
- **CSV columns**: `compound_largest_group_size`, `compound_singleton_fraction`

---

### M19 — Bridge-Edge Contraction Depth

- **Scalar**: `bridgeEdgeProportion = |bridges| / |edges|`, `meanContractionDepth = avg(chain_length over bridges)`
- **Per-element**: `(bridgeEdgeId, chainLength)` tuples
- **Backend change**:
  - `src/graph/builder.py` — when creating a bridge edge, record the contracted chain length on the edge data (e.g. `chain_length=3`)
  - `src/viz/app.py` — pass `chain_length` through in the API response edge data
- **Frontend**: read `chain_length` from edge data on rendered bridge edges; sum / count for scalars
- **Overlay**: small `k=N` label at the midpoint of each bridge edge
- **Conflicts**: none — bridges already have a distinct color
- **CSV columns**: `bridge_edge_proportion`, `mean_contraction_depth`
- **Risk**: bridge edges are only created when the user activates the visibility toggle on intermediate node types (CWE, TI). The metric is meaningful only when bridges exist; report `0` and `null` in CSV otherwise.

---

### M25 — Type-Pair Crossing Decomposition

- **Scalar**: top-3 type pairs by crossing count, plus a single `crossings_top_pair_share` (fraction of all crossings concentrated in the most-crossing pair)
- **Per-element**: extend `CrossingInfo` with `edgeAType`, `edgeBType`
- **Overlay**: color the existing red dots by type pair (categorical palette, ≤9 distinct pairs in practice for PAGDrawer)
- **Conflicts**: with M2 (radio group, see M2)
- **CSV columns**: `crossings_top_pair_share`, `crossings_top_pair_label`
- **Note**: avoid two CSV columns per type pair (would explode column count); the top-pair share is enough for a paper table.

---

### M20 — Edge Consolidation Ratio

- **Scalar**: `meanEcrWeighted` (mean ECR weighted by group size)
- **Per-element**: `(parentId, ecr)` tuples
- **Algorithm**: for each compound parent — count raw incoming/outgoing edges and synthetic incoming/outgoing edges; ECR = raw / synthetic per parent
- **Overlay**: append `ECR×N.M` to each compound parent's existing label, e.g. `AV:N / AC:L / PR:N / UI:N (×5)  ECR×3.4`
- **Conflicts**: with M21 (both modify compound labels). Resolution: a single "Compound annotations" overlay group with checkboxes for "Group size" (M21) and "ECR" (M20); when both on, label is `(×5  ECR×3.4)`
- **CSV columns**: `mean_ecr_weighted`
- **Risk**: only meaningful in outcomes-mode merge. In prereqs mode, ECR = 1 trivially. Report `null` outside outcomes mode.

---

### M3 — Angular Resolution at Nodes

- **Scalar**: `minAngularResolutionDeg` (minimum across all nodes), `meanAngularResolutionNormalized` (each node's smallest gap divided by ideal `2π/k`, averaged)
- **Per-element**: `(nodeId, smallestGapAngle, ideal)` tuples for the worst N nodes
- **Algorithm**: for each visible node with ≥ 2 incident edges, compute incidence angles via `arctan2`, sort, take cyclic differences, find min
- **Overlay**: small arc inside the narrowest gap at each "bad" node (gap < 60% of ideal). Color by goodness — red (very narrow) to yellow (60% threshold)
- **Conflicts**: none (new visual element type)
- **CSV columns**: `min_angular_resolution_deg`, `mean_angular_resolution_normalized`

---

### M24 — Column Purity

- **Scalar**: `columnPurity` (fraction of nodes whose layout column matches their type's expected column)
- **Per-element**: list of impure node IDs
- **Algorithm**: type → expected column index already in `getColumnPositions()` in `layout.ts`. For each visible node, compute its layout column from `n.position('x')` with a tolerance (±10% of expected column-center). Compare to expected.
- **Overlay**: draw a halo (large semi-transparent ring) around impure nodes
- **Conflicts**: none
- **CSV columns**: `column_purity`
- **Risk**: dagre doesn't expose column indices directly; we need a tolerance heuristic on x-position. Document the tolerance.

---

### M5 — Edge Length Per-Edge Tinting

- **Scalar**: already exported (`edge_length_cv`); no new scalar
- **Per-element**: `(edgeId, deviationFromMean)` tuples
- **Overlay**: tint each edge by deviation from the mean — cool color (blue) for shorter than mean, warm color (red) for longer. Saturation proportional to magnitude. Existing edge-type colors are replaced for the duration of this overlay
- **Conflicts**: with the entire edge-color scheme. Resolution: this overlay swaps the edge color stylesheet temporarily; only one "edge tint" overlay can be active at a time. Add a radio group "Edge tint:" with options (none / by-length-deviation / future M4)
- **CSV columns**: none new (covered by `edge_length_cv`)
- **Defer if hard**: this is the most complex visualization to plumb (Cytoscape stylesheets need dynamic per-element style overrides). If implementation gets messy, ship without M5 in this batch.

---

### M8 — Bbox Compactness Shading

- **Scalar**: `compactness = inkArea / bboxArea` where `inkArea = Σ_v π·r² + Σ_e ‖e‖·strokeWidth`
- **Per-element**: none
- **Overlay**: fill the existing blue bbox with a shading proportional to compactness — denser fill = higher compactness. Visualization is a single filled rectangle behind the graph
- **Conflicts**: none
- **CSV column**: `compactness`
- **Note**: the shading is a single global fill, not per-region. That's the right granularity — readers don't want a heatmap of where ink lives.

---

## New Debug Overlay Modal

### Layout

```
┌───────────────────────────────────────────────────────┐
│ 🔍 Debug Overlay Settings                  [×]      │
├───────────────────────────────────────────────────────┤
│                                                       │
│ Presets:                                              │
│   [ 🎯 Crossings analysis ]                           │
│   [ 📐 Layout diagnostics ]                           │
│   [ 🔗 Reduction transparency ]                       │
│   [ ◌  Defaults ]   [ ⊘ Clear all ]                  │
│                                                       │
├───────────────────────────────────────────────────────┤
│                                                       │
│ Existing overlays:                                    │
│   ☑ Edge crossings (red dots)                        │
│   ☑ Drawing area (blue rectangle)                    │
│   ☑ Mean edge length (green line)                    │
│   ☑ Std-dev (orange line)                            │
│                                                       │
│ Crossings — color by:                                │
│   ◯ none (default red)                               │
│   ◯ angle (M2)                                        │
│   ◯ type pair (M25)        [legend ▾]                │
│                                                       │
│ Compound annotations:                                 │
│   ☑ Group size ×N (M21)                              │
│   ☐ ECR×N.M (M20)                                    │
│                                                       │
│ Per-element diagnostics:                             │
│   ☐ Bridge contraction depth labels (M19)            │
│   ☐ Angular resolution arcs (M3)                     │
│   ☐ Column purity halos (M24)                        │
│                                                       │
│ Whole-graph annotations:                             │
│   ☐ Aspect ratio in bbox label (M9)                  │
│   ☐ Compactness fill in bbox (M8)                    │
│                                                       │
│ Edge tint:                                            │
│   ◯ none (default colors by edge type)               │
│   ◯ length deviation (M5)                            │
│                                                       │
└───────────────────────────────────────────────────────┘
```

### Presets

Five named presets at the top of the modal. Clicking a preset sets the toggle state below to a defined configuration; the user can then tweak before applying.

| Preset | Activates |
|--------|-----------|
| **🎯 Crossings analysis** | Edge crossings (dots) + Crossings color = type pair (M25) + Aspect ratio (M9). M2 angle coloring is one click away if needed. |
| **📐 Layout diagnostics** | Drawing area (blue bbox) + Aspect ratio (M9) + Mean edge length (green) + Std-dev (orange) + Angular resolution arcs (M3) + Column purity halos (M24) |
| **🔗 Reduction transparency** | Bridge contraction depth labels (M19) + Compound annotations: Group size (M21) + ECR (M20) |
| **◌ Defaults** | Just the existing 4 overlays; no new ones. (= the v2.x behavior before this plan) |
| **⊘ Clear all** | Everything off. |

Preset names are persisted in localStorage as the last-applied state, so reopening the modal doesn't lose context.

### Reach

The Statistics modal's existing **🔍 Show debug overlay** button changes:
- **Single click** still toggles overlays on/off with last-used settings (default preset on first use: "Defaults")
- A small ⚙️ next to it opens this **Debug Overlay Settings** modal

The button label reflects which overlays are currently active, e.g. `🔍 Debug overlays (3 active)`.

### State persistence

Overlay selection persists in `localStorage` under key `debugOverlayState_v1`. No backend involvement.

---

## Implementation Phases

Each phase ships on its own stage sub-branch under the umbrella `feature/metrics-roadmap`, merging back to the umbrella when its acceptance criteria pass. The umbrella merges to `main` after Paper Stage 7 per the Master roadmap. Phase 5 of this plan (Stage 8 in the Master roadmap) ships separately on `feature/visualization-surface` off `main` after the umbrella merge.

### Phase 1 — Foundation (extraction + quick wins)

1. **Existing-overlay extraction** into `debugOverlay.ts` (see "Existing-Overlay Extraction" above)
2. New Debug Overlay Settings modal scaffold + preset button row + per-overlay checkbox grid
3. Per-overlay state machine + localStorage persistence
4. M9 (aspect ratio label)
5. M21 (generalized group cardinality badges)

End state: every existing overlay individually toggleable; presets work; AR shown in bbox label; group-size badge consistent across compound types.

### Phase 2 — Crossings refinement

- M2 (crossing angle math + dot coloring)
- M25 (type-pair crossing decomposition + dot coloring)
- Radio-group UI for "Crossings color by"

End state: crossings tell two new stories (angle quality, type-pair concentration).

### Phase 3 — Bridges and merges

- Backend M19 (chain_length plumbing)
- M19 frontend (label rendering + scalars)
- M20 (ECR computation + label addition)

End state: the two reduction mechanisms (bridges, merges) are visually quantified.

### Phase 4 — Layout diagnostics

- M3 (angular resolution arcs)
- M24 (column purity halos)

End state: layout problems pop visually.

### Phase 5 — Surface treatments

- M5 (edge length deviation tint) — defer if hard
- M8 (compactness shading)

End state: visual richness for paper figures.

---

## Acceptance Criteria

- [ ] All 10 ✅ metrics appear as columns in the Drawing Quality CSV export
- [ ] All 10 ✅ metrics have a corresponding visual overlay
- [ ] Debug Overlay Settings modal exposes per-overlay toggles + 5 named presets
- [ ] Modal state persists across page reload (localStorage with version-suffixed key)
- [ ] Existing 4 overlays still work and are individually toggleable
- [ ] No new overlay can be applied to a hidden / exploit-hidden element
- [ ] Toggling any overlay does not change the computed metric values
- [ ] Backend `chain_length` exposed for bridge edges
- [ ] Backend `chain_length` covered by a unit test
- [ ] Each new metric has at least one unit test in `metrics.test.ts`
- [ ] Existing overlay extraction does not change observable behavior of the existing 4 overlays
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
| 5 | Modal grows beyond ~12 toggles → cognitive load | Presets at the top mitigate this; per-section grouping keeps the rest navigable |
| 6 | localStorage state may carry stale overlay names after a future renaming | Version the localStorage schema (`debugOverlayState_v1`) and reset on version mismatch |
| 7 | CSV column count grows substantially | Keep ordering consistent; document in domain doc; no other consumers depend on column order |
| 8 | The extraction step (Phase 1, item 1) might break the existing overlays in subtle ways | Run the existing test suite immediately after extraction, before adding any new code |

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
- `frontend/js/ui/debugOverlay.ts`
- `frontend/js/ui/debugOverlay.test.ts`

**Modified — major**:
- `frontend/js/features/metrics.ts` — 10 new computations + per-element data structures
- `frontend/js/features/metrics.test.ts` — tests for each new computation
- `frontend/js/ui/statistics.ts` — surface new metrics in table; replace inline overlay code with imports; "Debug Overlay" button → modal
- `frontend/js/config/constants.ts` — new pseudo-element styles for M3, M24, M19, etc.
- `frontend/index.html` — modal markup
- `frontend/css/styles.css` — modal layout, overlay markers, theme variants
- `frontend/js/main.ts` — wire modal globals

**Modified — minor (M19 backend)**:
- `src/graph/builder.py` — record chain length on bridge edges
- `src/viz/app.py` — pass through to API
- `tests/test_builder.py` — M19 backend test

**Documentation updates after implementation**:
- `Docs/_domains/StatisticsModal.md` — describe the new Debug Overlay modal
- `Docs/_domains/DrawingQualityMetrics.md` — list all new metrics with formulas
- `Docs/_dailyNotes/...-Extended_Metrics.md` — implementation log
