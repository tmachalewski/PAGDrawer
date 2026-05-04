# Statistics Modal

This document describes the **📊 Statistics modal** — the dedicated UI for inspecting graph counts, comparing them against the backend, viewing drawing-quality metrics, and exporting paper-ready CSV snapshots.

For the underlying drawing-quality math, see [`DrawingQualityMetrics.md`](DrawingQualityMetrics.md). For the backend stats endpoint and graph schema, see [`GraphNodeConnections.md`](GraphNodeConnections.md).

---

## What it's for

The Statistics modal answers four classes of question:

1. **What's actually on screen right now?** — live counts from Cytoscape, including any frontend-added pseudo-nodes (env VCs, merge compounds)
2. **Does it match the backend?** — same counts as `/api/stats`, which sees only the NetworkX graph
3. **What does the graph look like aesthetically?** — Purchase-style edge crossings, drawing area, edge length CV
4. **Can I capture this for my paper?** — single-row CSV export per click; user concatenates rows in a spreadsheet across reduction steps

It is intentionally **observational** — opening the modal never modifies the graph. The only state the modal leaves behind is a debug overlay (red dots / blue rectangle / green ruler / orange std-dev line) when the user explicitly toggles it.

---

## Layout

The modal opens at a wide max-width (1100 px, 95 % of viewport) and arranges its content in a four-row layout, with rows 2 and 3 splitting into two columns:

```
┌───────────────────────────────────────────────────────────┐
│ Visible (Live)              Backend Graph                 │  Row 1: totals
├───────────────────────────────────────────────────────────┤
│ Nodes by Type        │  Edges by Type                     │  Row 2: per-type
├───────────────────────────────────────────────────────────┤
│ Clean Attack Graph   │  Drawing Quality Metrics           │  Row 3: derived
│ Metrics              │  + Show debug overlay  + Export CSV │
├───────────────────────────────────────────────────────────┤
│ ⚠️ Interpretation notes (collapsible)                     │  Row 4: notes
└───────────────────────────────────────────────────────────┘
```

Below 900 px viewport, rows 2 and 3 collapse to a single column.

---

## Row 1 — Live vs Backend totals

Two cards side by side. Their divergence is intentional and load-bearing:

| Card | Source | What it includes |
|------|--------|------------------|
| **Visible (Live)** | `cy.nodes().filter(...)`, `cy.edges().filter(...)` | Current Cytoscape view. Excludes `exploit-hidden`, debug overlay nodes, and the synthetic `UNIT_EDGE` / `UNIT_EDGE_STD` debug edges. **Includes** UI/AC environment VCs (added by the frontend on page load) and active CVE merge compound parents. |
| **Backend Graph** | `GET /api/stats` | NetworkX graph only. **Excludes** UI/AC env VCs (the backend stopped emitting them in v2.0); excludes merge compounds (a frontend-only concept). |

The interpretation note panel explicitly calls out the expected discrepancies (e.g. "HAS_STATE: 2 in backend, 4 in live").

---

## Row 2 — Per-type counts

Two sorted tables: nodes by type, edges by type. Both built from live Cytoscape collections, sorted by count descending.

These are the same totals shown in Row 1 broken down by `data('type')`. Useful for confirming intuitions like "the merge button is doing what I expect — see, the CVE count dropped and CVE_GROUP count went up".

---

## Row 3 — Derived metrics

### Clean Attack Graph Metrics (left column)

A small table of counts that **strip structural artifacts** so you can compare the actual attack-graph content across reduction steps:

| Row | Computation |
|-----|-------------|
| Attack graph nodes (excl. artifacts) | live nodes minus ATTACKER, COMPOUND, BRIDGE, CVE_GROUP |
| Attack graph edges (excl. artifacts, synthetic) | live edges with no `synthetic` flag and neither endpoint in the artifact set |
| Unique CVE IDs | distinct base IDs (strip `:dN` and `@...` from CVE node IDs) |
| Initial-state VCs (in Initial State box) | VC nodes with `is_initial: true` (the AV:N / PR:N / UI / AC inside ATTACKER_BOX) |

### Drawing Quality Metrics (right column)

| Row | Source |
|-----|--------|
| Edge crossings (raw) | `findCrossings(edges).length` |
| Edge crossings (normalized, Purchase) | `1 − raw / max_possible`, max_possible per Purchase 2002 |
| Edge crossings per edge | `raw / |E|` |
| Drawing area (logical units²) | bounding box of node centers |
| Area per node (logical units²) | `drawing_area / |V|` |
| Edge length CV | population std / mean of edge lengths |

Plus two non-aesthetic counts useful for paper context:

| Row | Source |
|-----|--------|
| Unique CVEs (graph) | same value as in the Clean Attack Graph table — repeated here so the Drawing Quality table is self-contained for the CSV export |
| Trivy vulnerabilities (scans) | sum of `vuln_count` across all uploaded scans, fetched from `/api/data/scans` when the modal opens |

The right column has **four action buttons**: 🔍 **Show debug overlay**, ⚙️ (debug overlay settings), 📥 **Export CSV**, and 📄 **Export JSON**.

The 🔍 button toggles all currently-enabled overlays on/off; its label reports how many are enabled (e.g. `🔍 Show debug overlay (3)`). The ⚙️ button opens the **Debug Overlay Settings modal** described below.

---

## Row 4 — Interpretation notes

A collapsible `<details>` block enumerating common counting and interpretation pitfalls:

1. Live vs Backend divergence — UI/AC env VCs and merge compounds live frontend-only
2. Structural artifacts (ATTACKER, COMPOUND, BRIDGE, CVE_GROUP) inflate raw counts
3. Duplication sources — 2-layer model duplicates CVEs across L1/L2; chain-depth produces `:d0` / `:d1`; granularity sliders multiply further
4. Visibility toggles can either decrease or increase edge counts (bridge edges are added when types are hidden)
5. Environment filtering (UI/AC) dims rather than removes — filtered CVEs still appear in counts
6. CAN_REACH mixes ATTACKER→HOST and INSIDE_NETWORK→L2-host edges
7. HAS_STATE: 2 in backend, 4 in live (after env VCs are added)
8. Drawing-quality metrics: Purchase normalization, logical (zoom-invariant) coordinates, population std dev for the CV

These are written out so the user doesn't have to re-derive them when reading the numbers a week later.

---

## CSV export

Single click → single-row CSV downloads as `pagdrawer-metrics-YYYY-MM-DD-HH-mm.csv`.

Columns:

```
nodes,edges,unique_cves,trivy_vuln_count,crossings_raw,crossings_normalized,crossings_per_edge,drawing_area,bbox_width,bbox_height,area_per_node,edge_length_cv,aspect_ratio,compound_groups_count,compound_largest_group_size,compound_singleton_fraction,crossings_mean_angle_deg,crossings_min_angle_deg,crossings_right_angle_ratio,crossings_top_pair_share,crossings_top_pair_label,stress_per_pair,stress_per_pair_normalized_edge,stress_per_pair_normalized_diagonal,stress_per_pair_normalized_area,stress_unreachable_pairs,stress_reachable_pairs
```

Two variable-cardinality dictionaries are intentionally **not** flattened into CSV because they would produce non-stable headers across runs:

- `metrics.compound_size_distribution` (M21) — compound-parent size → count
- `metrics.crossings_type_pair_distribution` (M25) — type-pair label → count

Both live in the JSON export and are rendered in the Statistics modal (M21 as a histogram-style row, M25 surfaced via the top-pair scalar). The `crossings_top_pair_label` CSV column is RFC 4180-quoted when its value contains a comma or double quote.

Workflow for the ESORICS paper:

1. Apply step (e.g. baseline → hide CWE/TI → merge by outcomes → exploit paths)
2. Open the Statistics modal
3. Click 📥 Export CSV
4. Each click is one row; concatenate them in a spreadsheet, add a "step" column manually, and you have your evaluation table

The CSV is intentionally label-free — keeps the frontend stateless and lets the user drive the workflow.

---

## JSON export (schema v1)

Click 📄 **Export JSON** and a `pagdrawer-metrics-YYYY-MM-DD-HH-mm.json` file downloads. Same metric values as the CSV, but bundled with a settings snapshot and build provenance so the file is self-describing and reproducible.

### Schema

```jsonc
{
  "schema_version": 1,
  "exported_at": "2026-05-04T12:00:00.000Z",   // ISO 8601 UTC
  "app_version": "1.0.0",                       // from frontend/package.json
  "git_sha": "fa9e45dc8a3b1e2f0c4d5a7b9e6f8a2c4b1d3e5f",  // build-time HEAD

  "data_source": {
    "type": "trivy",                             // "trivy" | "mock" | "unknown"
    "scans_uploaded_total": 3,                   // every scan currently uploaded
    "scans_in_current_graph": [                  // scans actually feeding this graph
      { "id": "scan-uuid-1", "name": "nginx:stable-trixie-perl", "vuln_count": 189 }
    ],
    "selection_was_implicit": false              // true ⇒ user picked "all" and the
                                                  // list above is the full upload set
  },

  "settings": {
    "granularity": {
      "HOST": "ATTACKER",
      "CPE":  "HOST",
      "CVE":  "CPE",
      "CWE":  "CVE",
      "TI":   "CWE",
      "VC":   "TI"
    },
    "skip_layer_2": false,
    "visibility_hidden": ["CWE", "TI"],          // sorted, deterministic
    "cve_merge_mode": "outcomes",                // "none" | "prereqs" | "outcomes"
    "environment_filter": { "ui": "N", "ac": "L" },
    "exploit_paths_only_active": false,         // true when "show only exploit paths" mode is on
    "force_refresh_on_last_rebuild": false,
    "layout": "dagre"
  },

  "metrics": {
    "nodes": 67,
    "edges": 88,
    "unique_cves": 32,
    "trivy_vuln_count": 189,
    "crossings_raw": 32,
    "crossings_normalized": 0.9909,
    "crossings_per_edge": 0.3636,
    "drawing_area": 1523400.50,
    "bbox_width": 1820.00,
    "bbox_height": 837.04,
    "area_per_node": 22737.32,
    "edge_length_cv": 0.7748,
    "aspect_ratio": 0.42,
    "compound_groups_count": 4,
    "compound_largest_group_size": 8,
    "compound_singleton_fraction": 0.0,
    "compound_size_distribution": { "2": 1, "3": 1, "5": 1, "8": 1 },
    "crossings_mean_angle_deg": 67.4,
    "crossings_min_angle_deg": 23.1,
    "crossings_right_angle_ratio": 0.42,
    "crossings_top_pair_share": 0.31,
    "crossings_top_pair_label": "HAS_VULN×LEADS_TO",
    "crossings_type_pair_distribution": {
      "HAS_VULN×LEADS_TO": 10,
      "HAS_VULN×ENABLES":   7,
      "IS_INSTANCE_OF×LEADS_TO": 5
    },
    "stress_per_pair": 84.21,
    "stress_per_pair_normalized_edge": 0.0421,           // ÷ mean_edge_length (KK convention)
    "stress_per_pair_normalized_diagonal": 0.00012,      // ÷ sqrt(w² + h²)
    "stress_per_pair_normalized_area": 0.00018,          // ÷ sqrt(drawing_area)
    "stress_unreachable_pairs": 12,
    "stress_reachable_pairs": 2168
  }
}
```

### Versioning

`schema_version` only bumps on **breaking** changes (renamed or removed keys). Adding new metric fields under `metrics` is non-breaking — schema stays at v1.

### Reproducibility

- `git_sha` is injected at build time from `git rev-parse HEAD` (Vite `define`). In dev mode it reflects HEAD even with uncommitted changes — clean tree recommended for paper figures.
- `settings` is captured at the same moment metrics are computed (when the modal opens or refreshes), so the file's settings always match its numbers.
- **Exploit paths gap:** `exploit_paths_only_active: true` does not capture the seed selection that triggered the hiding. Reproducing an exploit-paths state requires manually re-triggering the same seed in the new session.

### Why JSON in addition to CSV

| Concern | CSV | JSON |
|---------|-----|------|
| Spreadsheet-native | ✅ | ❌ |
| Nested structures (settings tree) | ❌ | ✅ |
| Type fidelity (numbers vs strings, nulls) | ❌ | ✅ |
| Reproducibility (settings recoverable from the export) | ❌ | ✅ |

CSV stays the default for paper-table workflows; JSON is for archival, programmatic post-processing, and reviewer reproducibility.

---

## Debug overlay

The 🔍 button toggles overlays on/off. Each overlay is **independently** toggleable via the ⚙️ Debug Overlay Settings modal. Six overlays are available:

| Color / form | Marks | Underlying value | Default |
|--------------|-------|------------------|---------|
| 🔴 Red dots | One per counted edge crossing — color follows the **Crossings color by** radio: `none` (default red), `angle` (M2: red→yellow→green by acuteness), `typePair` (M25: categorical palette per type-pair) | `findCrossings(edges)[*].point` + `.angle` + `.edgeAType` × `.edgeBType` | on |
| 🔵 Blue dashed rectangle | Drawing area bounding box (label: `W × H`, optionally `(AR = …)`) | `computeBoundingBox(visibleNodes)` | on |
| 🟢 Green solid line | Mean edge length, drawn horizontally above the bbox | `computeMeanEdgeLength(edges)` | on |
| 🟠 Orange dashed line | Population std dev of edge lengths, drawn above the green line | `computeEdgeLengthStd(edges)` | on |
| Bbox label suffix `(AR = 0.42)` (M9) | `min(w,h) / max(w,h)` of the bbox | `computeAspectRatio(bb)` | off |
| Compound label suffix `(×N)` (M21) | Member count for every compound parent (idempotent: skips parents whose label already ends with `(×<digits>)`, e.g. CVE_GROUP) | `computeCompoundCardinality()` | off |
| Node fills coloured by graph distance from clicked source (M1) | Click any node → red→yellow→green gradient by symmetrised graph distance; unreachable = translucent grey; source = black with yellow border | `computeAPSP` + `symmetrizedDistance`. See [`StressMetric.md`](StressMetric.md) § Visualisation. | off |
| Floating pair-distance panel (M1) | Click two nodes in sequence → upper-right panel shows both directed distances, the symmetrised distance, and the Euclidean (layout) distance | same as above | off |

All overlay shapes are added as Cytoscape pseudo-nodes/edges with custom `type` values (`CROSSING_DEBUG`, `AREA_DEBUG`, `UNIT_EDGE_NODE`, `UNIT_EDGE`, `UNIT_EDGE_STD`). They zoom and pan with the graph, ignore mouse events, and are explicitly filtered out of every metric computation so toggling the overlay never changes what the metrics report.

The 🔍 button label reflects the count of enabled overlays (`🔍 Show debug overlay (4)`). When overlays are rendered the button switches to `❌ Hide debug overlay`.

### Debug Overlay Settings modal (⚙️)

A dedicated modal that lets the user toggle each overlay individually and apply named presets. Layout:

```
┌──────────────────────────────────────────────────────┐
│ 🔍 Debug Overlay Settings                  [×]      │
├──────────────────────────────────────────────────────┤
│ Presets:                                             │
│   [🎯 Crossings analysis]  [📐 Layout diagnostics]  │
│   [🔗 Reduction transparency]  [◌ Defaults]          │
│   [⊘ Clear all]                                       │
│                                                       │
│ Existing overlays:                                    │
│   ☑ Edge crossings (red dots)                        │
│   ☑ Drawing area (blue rectangle)                    │
│   ☑ Mean edge length (green line)                    │
│   ☑ Std-dev (orange line)                            │
│                                                       │
│ Crossings — color dots by:                            │
│   ◯ none (default red)                               │
│   ◯ angle (M2)        red acute → green ≈ 90°        │
│   ◯ type pair (M25)   categorical palette            │
│                                                       │
│ New overlays:                                         │
│   ☐ Aspect ratio in bbox label (M9)                  │
│   ☐ Compound group size ×N (M21)                     │
│                                                       │
│ Stress visualisation (M1):                            │
│   ☐ Color nodes by graph distance from clicked      │
│     source                                            │
│   ☐ Show pair distances on click                     │
└──────────────────────────────────────────────────────┘
```

Five preset configurations:

| Preset | Effect |
|--------|--------|
| 🎯 **Crossings analysis** | Crossings dots on (colored by **type pair**, M25) + aspect ratio on; everything else off. |
| 📐 **Layout diagnostics** | Bbox + mean + std-dev + aspect ratio; crossings off. |
| 🔗 **Reduction transparency** | Compound-cardinality badges only. |
| ◌ **Defaults** | The original four overlays on; new ones off. |
| ⊘ **Clear all** | Every overlay off. |

State persists in `localStorage` under the versioned key `debugOverlayState_v1`. A future schema change bumps the version suffix to invalidate stale state cleanly.

Module: `frontend/js/ui/debugOverlay.ts` — exports `showDebugOverlay`, `hideDebugOverlay`, `getOverlayState`, `setOverlayState`, `applyPreset`, `countEnabledOverlays`, `isDebugOverlayActive`, `validateState`, plus `openDebugOverlayModal` / `closeDebugOverlayModal` for the modal globals.

Dark-theme debug overlay on a real Node.js Alpine scan:

![Debug overlay (dark theme)](../../examples/_UI/UI-Debug%20Screenshot%202026-04-21%20185015.jpg)

Same overlay in the light theme:

![Debug overlay (light theme)](../../examples/_UI/UI-Debug-Light%20Screenshot%202026-04-21%20185347.jpg)

---

## Why a separate modal?

Before this feature, the live node/edge totals were tucked inside the Settings modal next to the granularity sliders — two clicks deep, no room for richer info, no place to put interpretation notes.

A dedicated modal:

- Surfaces the totals one click from the toolbar
- Has space for per-type breakdowns and derived metrics without crowding the slider UI
- Provides a natural home for the CSV export and debug overlay buttons
- Makes the Live/Backend divergence visible (was previously hidden because only one number was shown)

The Settings modal kept the per-type counts that show up next to each slider (those are about granularity, not stats) but offloaded everything else.

---

## Implementation

| File | Role |
|------|------|
| `frontend/index.html` | Modal markup, toolbar button, four Drawing Quality action buttons, Debug Overlay Settings modal |
| `frontend/css/styles.css` | Modal styles (cards, tables, notes, two-column responsive); Debug Overlay modal styles (`.debug-overlay-section`, `.debug-overlay-toggle`, presets row) |
| `frontend/js/ui/statistics.ts` | `openStatistics`, `closeStatistics`, `refreshStatistics`, section populators, CSV / JSON export wiring; delegates overlay drawing to `debugOverlay.ts` |
| `frontend/js/ui/debugOverlay.ts` | Per-overlay state machine, preset application, localStorage persistence, drawing pipeline for all 6 overlays, modal wiring |
| `frontend/js/ui/debugOverlay.test.ts` | State machine + preset + validateState + localStorage round-trip tests (23 tests) |
| `frontend/js/ui/sidebar.ts` | `updateLiveStats` simplified — only refreshes per-type slider counts now (totals moved here) |
| `frontend/js/main.ts` | Wires globals (`window.openStatistics`, `window.closeStatistics`) |
| `frontend/js/features/metrics.ts` | Computation + CSV serializer + JSON serializer (`metricsToJSON`, `buildMetricsJsonSnapshot`, `downloadMetricsJSON`) |
| `frontend/js/features/settingsSnapshot.ts` | `gatherCurrentSettings()` — async snapshot of granularity, visibility, merge mode, environment filter, exploit paths, layout |
| `frontend/js/config/buildInfo.ts` | Reads build-time `VITE_GIT_SHA` and `VITE_APP_VERSION` injected by `vite.config.ts` |
| `frontend/vite.config.ts` | Build-time `define` of `VITE_GIT_SHA` (from `git rev-parse HEAD`) and `VITE_APP_VERSION` (from `package.json`) |

The modal refreshes all sections every time it opens (`openStatistics → refreshStatistics`). No automatic re-refresh on graph changes — the user closes and reopens to see updated values. Intentional: refreshing a hidden modal would waste cycles, and the Live counts are only meaningful relative to a specific view.
