# 2026-04-20 - Statistics Modal + skip_layer_2 Option + Initial State Fixes

## Overview

Smaller but user-facing set of changes landing between the CVE Merge Modes feature and the graph-quality-metrics work. Three themes:

1. Split node/edge counts into a dedicated **📊 Statistics modal** so they're not tucked into Settings
2. Add a **"Skip Layer 2" config option** for building only the external attack surface
3. Fix two bugs in the **Initial State compound box** (duplicate UI/AC VCs; sprawling box layout)

Plus two small UX improvements: smoother zoom control, and compact layout for all compound-parent children.

---

## 1. Statistics Modal

### Motivation

The old "Total Nodes / Total Edges" widget lived inside the Settings modal, mixed in with granularity sliders. This hid the stats behind a two-click flow and gave no room for richer info like per-type breakdowns or interpretation notes.

### New modal

A dedicated "📊 Statistics" button in the toolbar opens a wide modal with four sections:

1. **Two side-by-side cards**: `Visible (Live)` counts from Cytoscape vs `Backend Graph` counts from `/api/stats`. Makes the Live/Backend divergence explicit.
2. **Nodes by Type (Live)** — sorted table of per-type node counts
3. **Edges by Type (Live)** — same for edges
4. **Clean Attack Graph Metrics** — derived counts with structural artifacts stripped:
   - Attack graph nodes (excludes ATTACKER, COMPOUND, BRIDGE, CVE_GROUP)
   - Attack graph edges (excludes synthetic merge edges and edges touching artifacts)
   - Unique CVE IDs (strips `:dN` depth and `@...` context suffixes)
   - Initial-state VCs (nodes in the ATTACKER_BOX compound)

Plus a collapsible "⚠️ Interpretation notes" section enumerating the 7 pitfalls discussed with the user before implementation (Live vs Backend divergence, duplication sources, visibility toggle side-effects, env-filter dimming, CAN_REACH mixed semantics, HAS_STATE count discrepancy, drawing metrics).

### Implementation

- `frontend/js/ui/statistics.ts` — new module with `openStatistics()`, `closeStatistics()`, `refreshStatistics()`
- `frontend/js/ui/sidebar.ts` — `updateLiveStats` now only refreshes per-type slider counts; the total-nodes / total-edges elements moved to the stats modal

---

## 2. skip_layer_2 Config Option

### Motivation

User wanted simpler graphs for node/edge counting and visibility metrics — not interested in modelling internal-network lateral movement (L2). Previously this required commenting out code.

### Implementation

- New boolean on `GraphConfig`:
  ```python
  skip_layer_2: bool = False
  ```
- `load_from_mock_data()` and `load_from_data()` in `builder.py` skip Phases 3 & 4 when the flag is set
- **`INSIDE_NETWORK` bridge node is still created** so the graph "ends" at the network boundary cleanly; `ENTERS_NETWORK` edges from L1 `EX:Y` nodes still connect to it
- New checkbox in Settings modal: "Skip Layer 2 (internal network)"
- 8 new tests in `TestSkipLayer2` (test_builder.py)

### Effect on counts (mock data)

| Mode | Nodes | Edges |
|------|-------|-------|
| Default (2-layer) | 415 | 462 |
| skip_layer_2 | 210 | 257 |

Roughly 2× reduction — L2 hosts/CPEs/CVEs/CWEs/TIs/VCs are all duplicated from L1 in the mock data, so skipping them halves most counts.

---

## 3. Initial State Box Fixes

### Bug 1: Duplicate UI/AC VCs

Previously:
- Backend's `_add_attacker_node()` created `VC:UI:N` and `VC:AC:L` as initial VCs
- Frontend's `updateEnvironmentVCs()` created *additional* `VC:ENV:UI` and `VC:ENV:AC` nodes

Result: four UI/AC nodes in the Initial State box instead of two. When the user changed environment settings, only the frontend `VC:ENV:*` nodes updated — the backend ones remained stale.

**Fix**: removed UI/AC VCs from the backend. The frontend now owns UI/AC entirely, using stable IDs (`VC:UI:N` / `VC:UI:R`, `VC:AC:L` / `VC:AC:H`) that get replaced cleanly on setting changes.

Also: new env VCs get positioned near existing ATTACKER_BOX siblings instead of at (0,0), and `compactCompoundChildren()` runs after creation to re-stack.

### Bug 2: Sprawling compound boxes

Dagre layout positioned compound children based on their graph-topology neighbors (edges to CPEs, VCs, etc.). For the ATTACKER_BOX with VCs connecting all over the graph, children spread across the full graph height, making the box huge.

Same problem for `CVE_GROUP` compounds when merging — large groups produced sprawling yellow rectangles.

**Fix**: `compactCompoundChildren()` in `graph/layout.ts`. After dagre completes:
- For each compound parent (`n.isParent() === true`)
- Preserve children's X position (correct column)
- Restack Y positions tightly around the centroid (15 px spacing, 30 px node height)
- Sort by original Y to preserve relative order

Makes compound boxes a compact vertical stack instead of a tall sparse column.

---

## 4. Smoother Zoom

Cytoscape's default `wheelSensitivity` of 1 produced coarse zoom jumps — tiny scroll movements could fly past the level of detail you wanted. Lowered to 0.3 and added `minZoom: 0.05` / `maxZoom: 5` bounds.

Small change, big UX improvement.

---

## 5. Files

### Statistics modal
- `frontend/js/ui/statistics.ts` (new)
- `frontend/index.html` (new button + modal markup)
- `frontend/css/styles.css` (modal styles, stats card/table/notes)
- `frontend/js/main.ts` (wire globals)
- `frontend/js/ui/sidebar.ts` (simplified `updateLiveStats`)

### skip_layer_2
- `src/core/config.py` (field + serialization)
- `src/graph/builder.py` (skip L2 phases)
- `src/viz/app.py` (accept bool in `/api/config` payload)
- `tests/test_builder.py` (`TestSkipLayer2` — 8 tests)
- `frontend/index.html` (Settings modal checkbox)
- `frontend/js/ui/modal.ts` (read/write the flag)

### Initial State fixes
- `src/graph/builder.py` (remove UI/AC from `_add_attacker_node`)
- `frontend/js/features/environment.ts` (unified stable-ID env VC upsert, position near siblings)
- `frontend/js/graph/layout.ts` (`compactCompoundChildren`, post-dagre stop callback)
- `frontend/js/graph/core.ts` (`wheelSensitivity: 0.3`, zoom bounds)

---

## 6. Test Counts

- Backend: +8 tests (`TestSkipLayer2`)
- Frontend: existing tests unchanged; new statistics module is UI-facing (not unit-tested)

---

## 7. Git Flow

Merged to master as commits:
- `a627c7b` — Initial State VC duplication + compact compound layout
- `a56d1bf` — Smoother zoom
- `b4b6272` — skip_layer_2 config option
- `0a4589a` — Statistics modal + skip-layer-2 settings integration

No feature branch for this batch — each was small enough to commit directly on master, per the conversation flow.
