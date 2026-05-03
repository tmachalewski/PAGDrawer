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

The right column also has **two action buttons**: 🔍 **Show debug overlay** and 📥 **Export CSV**.

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
nodes,edges,unique_cves,trivy_vuln_count,crossings_raw,crossings_normalized,crossings_per_edge,drawing_area,area_per_node,edge_length_cv
```

Workflow for the ESORICS paper:

1. Apply step (e.g. baseline → hide CWE/TI → merge by outcomes → exploit paths)
2. Open the Statistics modal
3. Click 📥 Export CSV
4. Each click is one row; concatenate them in a spreadsheet, add a "step" column manually, and you have your evaluation table

The CSV is intentionally label-free — keeps the frontend stateless and lets the user drive the workflow.

---

## Debug overlay

Toggled by the 🔍 button next to Export CSV. Draws four visual aids on the actual graph (not in the modal):

| Color | Marks | Underlying value |
|-------|-------|------------------|
| 🔴 Red dots | One per counted edge crossing | `findCrossings(edges)[*].point` |
| 🔵 Blue dashed rectangle | Drawing area bounding box | `computeBoundingBox(visibleNodes)` |
| 🟢 Green solid line | Mean edge length, drawn horizontally above the bbox | `computeMeanEdgeLength(edges)` |
| 🟠 Orange dashed line | Population std dev of edge lengths, drawn above the green line | `computeEdgeLengthStd(edges)` |

All four are added as Cytoscape pseudo-nodes/edges with custom `type` values (`CROSSING_DEBUG`, `AREA_DEBUG`, `UNIT_EDGE_NODE`, `UNIT_EDGE`, `UNIT_EDGE_STD`). They zoom and pan with the graph, ignore mouse events, and are explicitly filtered out of every metric computation so toggling the overlay never changes what the metrics report.

The button toggles between `🔍 Show debug overlay` and `❌ Hide debug overlay` based on whether any debug elements currently exist. State is kept in `debugElementIds[]` in `statistics.ts`.

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
| `frontend/index.html` | Modal markup, toolbar button |
| `frontend/css/styles.css` | Modal styles (cards, tables, notes, two-column responsive) |
| `frontend/js/ui/statistics.ts` | `openStatistics`, `closeStatistics`, `refreshStatistics`, the section populators, debug overlay control |
| `frontend/js/ui/sidebar.ts` | `updateLiveStats` simplified — only refreshes per-type slider counts now (totals moved here) |
| `frontend/js/main.ts` | Wires globals (`window.openStatistics`, `window.closeStatistics`) |

The modal refreshes all sections every time it opens (`openStatistics → refreshStatistics`). No automatic re-refresh on graph changes — the user closes and reopens to see updated values. Intentional: refreshing a hidden modal would waste cycles, and the Live counts are only meaningful relative to a specific view.
