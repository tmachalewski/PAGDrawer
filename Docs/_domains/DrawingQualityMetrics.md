# Drawing Quality Metrics

This document describes the graph-drawing aesthetics metrics implemented in PAGDrawer, following **Purchase, H.C. (2002) — "Metrics for Graph Drawing Aesthetics"**, *Journal of Visual Languages and Computing, 13(5), 501–516*.

These metrics are exposed via the **📊 Statistics modal** (toolbar button) and exported as CSV for paper-ready snapshots.

For the *how we built it* history, see `Docs/_dailyNotes/2026-04-20-15-55-Graph_Quality_Metrics.md`. For the original paper-writing guide that preceded this implementation, see `Docs/initial_graph_metrics_guide.md`.

---

## Three Metrics

### 1. Edge Crossings

The number of edge pairs whose line segments intersect in their interiors, excluding pairs that share an endpoint.

Three variants are reported, all derived from the same count:

| Variant | Formula | Range | Reads as |
|---------|---------|-------|----------|
| **Raw** | `crossings` | integer ≥ 0 | "32 crossings" |
| **Normalized (Purchase)** | `1 - crossings / max_possible` | [0, 1] | "score 0.99 out of 1.0" |
| **Per edge** | `crossings / \|E\|` | ≥ 0 | "0.36 crossings per edge" |

where `max_possible = C(|E|, 2) - Σ_v C(deg(v), 2)` — total non-adjacent edge pairs (pairs sharing a node can't cross, so they're subtracted).

Why three? Each tells a slightly different story:
- **Raw** is the most tangible ("I can count those dots on the graph")
- **Normalized** is the standardized academic score per Purchase
- **Per edge** is the most intuitive for sparse real-world graphs (PAGDrawer's normalized score is usually ~0.99 which sounds perfect but hides the real shape)

### 2. Drawing Area

`(max_x - min_x) × (max_y - min_y)` across the center-points of visible nodes. Units are **Cytoscape logical coordinates** — invariant under zoom and pan, so the number is stable no matter how the user has scrolled.

Center-point method rather than padded bounding box, matching Purchase's formulation. Compound parent nodes are included but don't affect the bounding box (their centroid falls within the span of their children).

### 3. Edge Length Coefficient of Variation

`std(lengths) / mean(lengths)` where `lengths[i] = Euclidean distance from edge source to edge target`, both measured in logical coordinates.

Population standard deviation (divide by N, not N−1). A value of 0 means all edges are the same length (uniform layout); higher values mean the drawing has both very short and very long edges, which Purchase correlates with reduced readability.

---

## What Counts as "Visible"

The metrics operate on the user's current view. The selector is Cytoscape's `:visible` (which covers `display: none` exclusions) with some additional filters:

| Node/edge kind | Included? | Why |
|---------------|----------|-----|
| Normal graph elements | ✅ | |
| Nodes/edges with `.exploit-hidden` class (exploit-paths filter) | ❌ | `display: none` via the filter; explicitly excluded |
| `env-filtered` nodes (dimmed by UI/AC) | ✅ | Still drawn — they contribute to visual clutter |
| `unreachable` nodes (dimmed) | ✅ | Same reasoning |
| `COMPOUND` parent (ATTACKER_BOX) | ✅ | Has no graph edges → no effect on crossings/EL-CV; centroid is within children → no effect on area |
| `CVE_GROUP` parent (merge compound) | ✅ | Same reasoning |
| `CROSSING_DEBUG` red dots | ❌ | Debug overlay — must not feed back into metrics |
| `AREA_DEBUG` rectangle | ❌ | Same |
| `UNIT_EDGE_NODE` / `UNIT_EDGE` / `UNIT_EDGE_STD` | ❌ | Debug overlay |

---

## What Does NOT Count as a Crossing

The segment-intersection test is **strict interior only**:

```
0 < t < 1  AND  0 < u < 1
```

This means:

- **Endpoint touches are not crossings.** Two edges meeting at a shared node (the classic hub/fan-out pattern) are skipped before geometry is even tested.
- **Collinear overlap is not a crossing.** Two edges on the same line that overlap partially have `denom = 0` and return `null`. Consistent with Purchase's definition.
- **T-junctions (endpoint landing on another edge) are not crossings.** The t or u parameter hits 0 or 1, excluded by strict inequality.

This is why a graph that *looks* visually tangled (because many edges fan out from a hub CVE) can have a surprisingly low crossing count. The debug overlay helps separate visual impression from counted reality.

---

## Debug Overlay

The Statistics modal has a **🔍 Show debug overlay** button that draws four visual markers on the graph. They zoom/pan with the graph, are non-interactive, and are excluded from metrics themselves.

### 🔴 Red dots — counted crossings

One red circle at each intersection point returned by `findCrossings()`. Direct visual verification: every dot is a counted crossing, and every counted crossing has a dot.

If you see obvious crossings with no red dot, the metric missed something (report it). If you see red dots that don't look like crossings, they likely arise from fan-out regions where endpoints coincide visually but don't share nodes.

### 🔵 Blue dashed rectangle — drawing area

Frames the bounding box. Label at the top-center reads `Drawing area  1732 × 987` in logical units. Makes the "area" metric tangible — the rectangle you see is what's being measured.

### 🟢 Green solid line — mean edge length

Horizontal reference line placed just above the bounding box, length equal to the computed mean. Label: `mean edge length: 123.4`. Acts as a visual "unit ruler" — compare any edge in the graph to this line to see whether it's shorter or longer than typical.

### 🟠 Orange dashed line — std dev

Placed above the green line, length equal to the **standard deviation** of edge lengths.

Why std dev, not variance? Variance has units of length² and can't be drawn to scale alongside a length-unit line. Std dev = √variance has the right units and represents "typical spread from the mean".

If the orange line is nearly as long as the green line, the edge-length CV is high (lots of variation). If much shorter, edges cluster tightly around the mean.

---

## CSV Export

For the ESORICS paper workflow: apply each reduction step manually, click **📥 Export CSV** in the Statistics modal, collect one CSV per step, concatenate in a spreadsheet.

Format (header row + one data row):

```
nodes,edges,crossings_raw,crossings_normalized,crossings_per_edge,drawing_area,edge_length_cv
67,88,32,0.9909,0.3636,1523400.50,0.7748
```

Filename: `pagdrawer-metrics-YYYY-MM-DD-HH-mm.csv`.

No step labeling or aggregation in-app — the user adds those in their sheet after combining rows. Keeps the frontend stateless.

---

## Interpretation Pitfalls

The Statistics modal's collapsible "⚠️ Interpretation notes" section flags these for the user:

1. **Normalized score looks deceptively high.** PAGDrawer graphs have many edges sharing hub nodes (one CPE → many CVEs, one CVE → many VCs), which inflates `adjacent_pairs` and keeps `max_possible` huge. Normalized scores cluster near 1.0 even when the graph is visually busy.
2. **Fan-out isn't a crossing.** Edges emanating from the same hub node visually overlap near the hub but correctly don't count.
3. **Drawing area is zoom-invariant.** Logical coordinates, not screen pixels. Scrolling doesn't change the number.
4. **Center-point method undercounts perceived area.** Actual on-screen area includes node sizes and their bounding boxes. Center-point gives a tighter/smaller number — fine for relative comparisons across reduction steps but not for absolute pixel-to-pixel matching.
5. **Edge length CV uses straight lines between node centers.** Cytoscape may render edges as Bezier curves for multi-edge pairs; the metric uses center-to-center distance regardless of rendered shape.

---

## Implementation

- **Module**: `frontend/js/features/metrics.ts` (~310 LOC)
- **Tests**: `frontend/js/features/metrics.test.ts` (35 unit tests, pure functions, no Cytoscape instance needed)
- **UI integration**: `frontend/js/ui/statistics.ts`
- **Cytoscape styles for overlay pseudo-nodes**: `frontend/js/config/constants.ts`

Key public exports of `metrics.ts`:

```typescript
computeMetrics() → DrawingMetrics | null
countCrossings(edges) → number
findCrossings(edges) → CrossingInfo[]
normalizeCrossings(crossings, edges) → number
computeDrawingArea(points) → number
computeBoundingBox(points) → BBox | null
computeMeanEdgeLength(edges) → number
computeEdgeLengthStd(edges) → number
computeEdgeLengthCV(edges) → number
metricsToCSV(m) → string
downloadMetricsCSV(m) → void
getVisibleNodePoints() → Point[]     // helper for overlay
getVisibleEdgeEndpoints() → EdgeEndpoints[]   // helper for overlay
```

All pure functions except `computeMetrics`, `getVisibleNodePoints`, `getVisibleEdgeEndpoints` (which depend on the live Cytoscape graph) and `downloadMetricsCSV` (triggers a browser download).

---

## References

- **Purchase, H.C. (2002)** — "Metrics for Graph Drawing Aesthetics." *Journal of Visual Languages and Computing*, 13(5), 501–516.
- **Di Bartolomeo et al. (2024)** — "Evaluating Graph Layout Algorithms: A Systematic Review." *Computer Graphics Forum.* (Uses EL-CV alongside Purchase's metrics.)
- **greadability.js** — https://github.com/rpgove/greadability. Considered but not used; we only needed `crossing`, so a 40-line inline implementation was preferred.
