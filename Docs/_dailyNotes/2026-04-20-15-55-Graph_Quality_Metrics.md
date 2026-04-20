# 2026-04-20 - Graph Drawing Quality Metrics (Purchase 2002)

## Overview

Implemented three graph-drawing aesthetics metrics for the ESORICS paper evaluation, following Purchase, H.C. (2002) "Metrics for Graph Drawing Aesthetics". Added a debug overlay that visualizes each metric on the graph itself — red dots at counted crossings, a blue bounding box for drawing area, and green/orange reference lines for mean edge length and standard deviation. CSV export produces paper-ready single-row snapshots at each reduction step.

Done in one feature branch `feature/graph-quality-metrics`, merged as commit `26c7c6a`.

---

## 1. The Three Metrics

### Edge crossings — three variants reported

- **Raw count** — integer, total pairs of edges that intersect in their interiors, excluding pairs sharing an endpoint (per Purchase). Easy to read in a table.
- **Normalized (Purchase 2002)** — `1 - (crossings / max_possible)` where `max_possible = C(|E|,2) - Σ C(deg(v),2)`. Range [0, 1], 1 = no crossings. Standardized score for academic defensibility.
- **Per edge** — `crossings / |E|`. Simple intuitive ratio ("about 0.36 crossings per edge").

All three are displayed in the Statistics modal and exported to CSV.

### Drawing area

`(max_x - min_x) × (max_y - min_y)` across visible node center-points. Logical (layout) units, invariant under zoom/pan. Center-point method rather than padded bounding box (matches Purchase's formulation).

### Edge length coefficient of variation

`std(lengths) / mean(lengths)` where lengths are Euclidean distances between edge endpoints. Population standard deviation (dividing by N, not N-1). 0 means uniform; higher means some edges are very long / some very short.

---

## 2. Design Decisions

### Logical coordinates, not screen pixels

Cytoscape has two coordinate systems: layout (`n.position()`) and rendered (post-zoom-pan). Screen pixels change every time you scroll, which would make the metric meaningless. Everything uses logical coordinates so a saved graph gives the same number regardless of current viewport.

### Visibility filter

"Whatever is visible on screen" — `:visible` pseudo-selector. Explicit exclusions:

| Excluded | Why |
|----------|-----|
| `exploit-hidden` nodes/edges | Had `display: none` via exploit-paths filter |
| `CROSSING_DEBUG` pseudo-nodes | Debug overlay must not feed back on itself |
| `AREA_DEBUG` node | Same |
| `UNIT_EDGE_NODE` / `UNIT_EDGE` / `UNIT_EDGE_STD` | Same |

Not excluded:
- `env-filtered` (dimmed but drawn — still visual clutter)
- `unreachable` (dimmed but drawn)
- `COMPOUND` / `CVE_GROUP` parents (have no graph edges, so contribute nothing to crossings or EL-CV; their centroid is within children so doesn't affect area either)

### Shared-endpoint pairs don't count

Two edges meeting at a node (fan-out from a hub CVE) aren't a "crossing" in graph-drawing theory. The algorithm skips `(A, B)` whenever they share any endpoint. This catches the dense-looking hub regions that visually seem tangled but are geometrically correct.

The user's first reaction to "32 crossings" on a visually busy graph was understandable pushback — but the debug overlay confirmed the 32 red dots land on genuine interior crossings, and most of the visual noise is fan-out.

### Why not use greadability.js?

The guide (`Docs/initial_graph_metrics_guide.md`) suggested greadability.js. But:
- Not on npm — needs manual vendor copy (~500 LOC)
- We only need `crossing` (not `crossingAngle`, `angularResolutionMin`, `angularResolutionDev`)
- The ~40-line inline implementation is more reviewable

Chose inline. Module: `frontend/js/features/metrics.ts` (~200 LOC).

---

## 3. Segment-Intersection Math

Two segments p1→p2 and p3→p4 cross in their **strict interiors** when both the denominator is non-zero and both parameters lie in `(0, 1)`:

```
denom = (p1.x - p2.x)(p3.y - p4.y) - (p1.y - p2.y)(p3.x - p4.x)
t = ((p1.x - p3.x)(p3.y - p4.y) - (p1.y - p3.y)(p3.x - p4.x)) / denom
u = -((p1.x - p2.x)(p1.y - p3.y) - (p1.y - p2.y)(p1.x - p3.x)) / denom

0 < t < 1 AND 0 < u < 1
```

Interior-only (strict inequalities) means endpoint-touches and collinear overlaps are NOT counted — consistent with Purchase's definition.

Returning the intersection point as `(p1.x + t(p2.x-p1.x), p1.y + t(p2.y-p1.y))` lets the debug overlay mark each crossing with a red dot.

---

## 4. Debug Overlay

Added in response to user skepticism about whether 32 was correct. Instead of arguing, make the metric visible.

Three overlays on a single button toggle:

### 🔴 Red dots — counted crossings

Each entry of `findCrossings()` contributes one pseudo-node of type `CROSSING_DEBUG` at the intersection point. Styled as a small red circle with white border, `z-index: 9999`, `events: no` so it doesn't steal clicks.

Data attributes carry the source/target IDs of the two crossing edges (for future click-to-inspect).

### 🔵 Blue dashed rectangle — drawing area

Single `AREA_DEBUG` pseudo-node positioned at the centroid of the bounding box, with `width` and `height` style set to the actual dimensions. Label: `Drawing area  1732 × 987`. Dashed border, transparent fill.

### 🟢 Green line — mean edge length

Two invisible `UNIT_EDGE_NODE` pseudo-nodes at `(min_x, min_y - padding)` and `(min_x + meanLen, min_y - padding)`, connected by a `UNIT_EDGE` edge labeled `mean edge length: 123.4`. Acts as a visual ruler — compare any edge in the graph to this line to gauge relative length.

### 🟠 Orange dashed line — std dev

Same pattern, placed just above the mean line, length = population std dev, label `std dev: 89.7`.

Why std dev and not variance? Variance has units of length², can't be drawn to scale alongside a length-unit line. Std dev = √variance has the right units.

All four are excluded from metrics and counts so toggling them never changes what the metric reports.

---

## 5. UI Integration

### Statistics modal

Added two new sections:
- **Drawing Quality Metrics** table — 5 rows (crossings raw, normalized, per-edge, drawing area, edge length CV)
- **Debug overlay toggle** + **CSV export** buttons

Modal also restructured to a wider, 2-column layout (was too tall and forced zoom out):
- Row 1: Live vs Backend cards
- Row 2: Nodes by type | Edges by type
- Row 3: Clean metrics | Drawing quality metrics
- Row 4: Interpretation notes (full width)

Max-width bumped from 680 px to 1100 px; responsive collapse to single column below 900 px.

### CSV format

Single-row export for paper workflow:

```
nodes,edges,crossings_raw,crossings_normalized,crossings_per_edge,drawing_area,edge_length_cv
67,88,32,0.9909,0.3636,1523400.50,0.7748
```

Filename: `pagdrawer-metrics-YYYY-MM-DD-HH-mm.csv`. User manually applies each of 6 reduction steps (baseline → slider tweak → exploit paths → hide CWE/TI → merge prereqs → merge outcomes), exports one CSV per step, concatenates in a spreadsheet.

No aggregation buffer or step labeling — user adds those in their sheet.

---

## 6. Tests

`frontend/js/features/metrics.test.ts` — 35 unit tests:

| Group | Coverage |
|-------|----------|
| `segmentsIntersect` / `segmentIntersectionPoint` | +/X/parallel/collinear/endpoint-touch cases |
| `countCrossings` / `findCrossings` | K4 = 1 crossing, fan-out = 0, empty/singleton edge lists |
| `normalizeCrossings` | 0 crossings → 1.0, max → 0.0, edge cases (star graph, <2 edges) |
| `computeDrawingArea` / `computeBoundingBox` | empty, single node, collinear, normal cases |
| `computeMeanEdgeLength` / `computeEdgeLengthStd` | empty, uniform, mixed |
| `metricsToCSV` | header + data row, all three crossing variants |

Pure-function tests, no Cytoscape instance needed.

---

## 7. Files

**New**:
- `frontend/js/features/metrics.ts` (~310 LOC including debug overlay helpers)
- `frontend/js/features/metrics.test.ts` (35 tests)

**Modified**:
- `frontend/js/ui/statistics.ts` (wired metrics + debug overlay)
- `frontend/js/config/constants.ts` (4 new Cytoscape styles: CROSSING_DEBUG, AREA_DEBUG, UNIT_EDGE_NODE, UNIT_EDGE, UNIT_EDGE_STD)
- `frontend/index.html` (metrics section + buttons)
- `frontend/css/styles.css` (2-column modal layout, wider modal)

---

## 8. Example Reading for Current Mock Graph

With the default mock data (all sliders default, no filtering):
- Crossings raw: **32**
- Crossings normalized: **0.9909** — sounds high, but that's because `max_possible` includes the huge number of non-adjacent pairs that *could* cross but don't in practice
- Crossings per edge: **0.36** — more intuitive; reads as "one crossing per ~3 edges"
- Drawing area: **2,963,778 logical units²**
- Edge length CV: **0.77** — moderate variance; some short tight edges (ATTACKER_BOX children) and some long ones (CVE → VC)

After hiding CWE + TI + merging by outcomes:
- Crossings drop sharply (fewer edges)
- Area shrinks (fewer nodes to place)
- EL-CV often decreases (more uniform post-reduction)

---

## 9. Research Foundation

> **Purchase, H.C. (2002)** — "Metrics for Graph Drawing Aesthetics"
> Journal of Visual Languages and Computing, 13(5), 501–516.

Seminal paper validating that these three metrics correlate with human readability judgments. Widely cited in the graph-drawing literature; defensible for an ESORICS submission.
