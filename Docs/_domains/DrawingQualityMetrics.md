# Drawing Quality Metrics

This document describes the graph-drawing aesthetics metrics implemented in PAGDrawer.

The edge-crossings metric follows **Purchase, H.C. (2002) — "Metrics for Graph Drawing Aesthetics"**, *Journal of Visual Languages and Computing, 13(5), 501–516*. The drawing-area, area-per-node, and edge-length-CV metrics are common graph-drawing aesthetics from the wider literature (force-directed layout / Bennett et al. 2007); they are not in Purchase 2002 specifically.

These metrics are exposed via the **📊 Statistics modal** (toolbar button) and exported as CSV for paper-ready snapshots.

For the *how we built it* history, see `Docs/_dailyNotes/2026-04-20-15-55-Graph_Quality_Metrics.md` and the bug-fix / metric-additions note `2026-05-03-18-57-Bug_Fixes_And_Metric_Additions.md`.

---

## Metrics

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

Center-point method rather than padded bounding box. Compound parent nodes are included but don't affect the bounding box (their centroid falls within the span of their children).

### 3. Area per Node

`drawing_area / |V|`. Same logical units as drawing area; normalized for graph size.

Easier to compare across reduction steps than raw area, because reduction usually changes both the area *and* the node count. Reads as "logical units² of canvas per node":

- Lower → denser drawing
- Higher → sparser, more whitespace per node

### 4. Edge Length Coefficient of Variation

`std(lengths) / mean(lengths)` where `lengths[i] = Euclidean distance from edge source to edge target`, both measured in logical coordinates.

Population standard deviation (divide by N, not N−1). A value of 0 means all edges are the same length (uniform layout); higher values mean the drawing has both very short and very long edges, which is generally correlated with reduced readability.

---

## Auxiliary counts (in CSV and Statistics modal)

Two non-aesthetic counts are also exported alongside the drawing-quality metrics so paper readers can correlate graph shape with vulnerability volume:

### Unique CVEs

Distinct base CVE IDs in the live graph. Computed from CVE node IDs by stripping the `:dN` chain-depth suffix and the `@...` granularity context, then deduplicating.

`unique_cves` differs from the visible CVE node count because:
- Granularity sliders may produce one CVE node per host or per CPE; the same base CVE ID then maps to multiple nodes
- Chain-depth-aware multi-stage attacks produce `:d0` and `:d1` variants of the same CVE ID

### Trivy Vulnerability Total

Sum of Trivy-reported per-package vulnerability entries across **all uploaded scans** (not just those in the current rebuild). Fetched from `/api/data/scans` when the Statistics modal opens.

This differs from `unique_cves` because Trivy reports one entry per affected package — a single CVE that touches three packages contributes three vuln entries but one unique CVE ID. See the related discussion in the daily note for an example (189 vulns → 103 unique CVEs in the `nginx_stable-trixie-perl` scan).

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

For the GD 2026 paper workflow: apply each reduction step manually, click **📥 Export CSV** in the Statistics modal, collect one CSV per step, concatenate in a spreadsheet.

The header row currently has **37 columns** spanning every metric exposed by the modal. The full ordered column list lives in [`StatisticsModal.md`](StatisticsModal.md) § "CSV export" so a single source of truth stays in sync with the implementation. Filename: `pagdrawer-metrics-YYYY-MM-DD-HH-mm.csv`.

`trivy_vuln_count` is left empty if the scan list cannot be fetched. Numeric columns are formatted with 4 decimals for [0,1] scores, 2 decimals for area/length/angle values, and integers as integers. The `crossings_top_pair_label` column is RFC 4180-quoted when it contains a comma or double quote.

For the **paper showcase plan** — which 5 reduction steps to apply in what order to produce the headline evaluation table — see [`MetricsPaperReference.md`](MetricsPaperReference.md) § 6.

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

> **Source pinning.** Line numbers in this section are accurate as of commit [`130f20b`](https://github.com/tmachalewski/PAGDrawer/commit/130f20b) (2026-05-05). Function names are stable identifiers — even if the line numbers drift, `grep -n 'export function NAME' frontend/js/features/metrics.ts` will resolve them.

- **Module**: `frontend/js/features/metrics.ts`
- **Tests**: `frontend/js/features/metrics.test.ts` (57 unit tests, pure functions, no Cytoscape instance needed)
- **UI integration**: `frontend/js/ui/statistics.ts` (table + export buttons), `frontend/js/ui/debugOverlay.ts` (per-overlay state machine + drawing pipeline)
- **Cytoscape styles for overlay pseudo-nodes**: `frontend/js/config/constants.ts`

Key public exports of `metrics.ts`:

```typescript
computeMetrics() → DrawingMetrics | null   // includes uniqueCves, aspectRatio (M9), compound* (M21)
countCrossings(edges) → number
findCrossings(edges) → CrossingInfo[]
normalizeCrossings(crossings, edges) → number
computeDrawingArea(points) → number
computeBoundingBox(points) → BBox | null
computeMeanEdgeLength(edges) → number
computeEdgeLengthStd(edges) → number
computeEdgeLengthCV(edges) → number
computeAspectRatio(bb) → number                                  // M9
computeCompoundCardinality() → CompoundCardinality               // M21 — live cy
computeCompoundCardinalityFromCounts(counts) → CompoundCardinality  // M21 — pure helper
computeCrossingAngle(a, b) → number                              // M2  — acute angle ∈ [0, π/2]
computeCrossingAngleStats(crossings, tolRad?)                    // M2  — {meanRad, minRad, rightAngleRatio}
computeTypePairCrossingStats(crossings)                          // M25 — {distribution, topPairLabel, topPairShare}
computeAcr() → {acrPrereqs, acrOutcomes, nodeCount}              // M22 — live cy
computeAcrFromKeys(cveData) → {acrPrereqs, acrOutcomes, nodeCount}  // M22 — pure helper
computeAPSP(nodeIds, edges, opts?) → Map<string, Map<string, number>>  // BFS APSP, default directed, unweighted
symmetrizedDistance(apsp, a, b) → number | undefined              // min of two directed paths
computeStress() → StressBundle                                   // M1  — raw + 3 normalisations
computeStressFromAPSP(nodes, apsp, layoutScale?)                 // M1  — pure helper
getVisibleNodesWithIds() → NodeWithPosition[]                    // visible non-debug nodes (broader set)
getStressEligibleNodes() → NodeWithPosition[]                    // visible non-debug nodes WITH ≥1 visible edge
                                                                  //   — used by computeStress so compound ghost-layers don't pollute the metric
computeBridgeStats() → BridgeStats                               // M19 — live cy
computeBridgeStatsFromList(edgeInfos)                            // M19 — pure helper
computeEcr() → EcrStats                                          // M20 — live cy
computeEcrFromList(perParent)                                    // M20 — pure helper
metricsToCSV(m, context?) → string
downloadMetricsCSV(m, context?) → void
metricsToJSON(m, context, settings, dataSource, now?) → string   // schema v1
downloadMetricsJSON(m, context, settings, dataSource) → void
buildMetricsJsonSnapshot(...) → MetricsJsonSnapshot
buildDataSourceSnapshot(scans) → DataSourceSnapshot
getVisibleNodePoints() → Point[]
getVisibleEdgeEndpoints() → EdgeEndpoints[]
```

All pure functions except `computeMetrics`, `computeCompoundCardinality`, `getVisibleNodePoints`, `getVisibleEdgeEndpoints` (live Cytoscape graph) and `downloadMetricsCSV` / `downloadMetricsJSON` (browser download).

### M1 — Stress (Purchase 2002)

The most-cited graph-drawing layout-quality metric. Reviewers expect it.

> **See [`StressMetric.md`](StressMetric.md) for the full explanation:** what stress measures, why it matters, the directed-vs-undirected adaptation we ship, and the visualisation plan.

Headline summary:

```
stress_per_pair = mean over reachable pairs of (‖p_i − p_j‖_layout − d_ij)²
```

PAGDrawer's graph is a directed DAG, so we run **directed BFS** for the APSP and use the **symmetrised distance** `d_ij = min(d(i→j), d(j→i))` for the metric — Euclidean is symmetric, the graph-side comparison must be too. Pairs unreachable in both directions are excluded from the mean and reported separately under `stress_unreachable_pairs`. See `StressMetric.md` § "What PAGDrawer ships" for why this beats both the strict-undirected and strict-directed alternatives.

Algorithm: `computeAPSP(nodeIds, edges, { directed?: boolean })` runs BFS from every node. BFS is the right algorithm for unweighted graphs — Dijkstra reduces to it but with heap overhead, Floyd-Warshall is O(|V|³). Default mode is directed; pass `{ directed: false }` for the undirected variant. Complexity is O(|V|·(|V|+|E|)). At the largest pipeline step in the nginx test scan (|V| ≈ 830, |E| ≈ 5,675) this runs in tens of milliseconds; after the granularity and visibility reductions ($|V| < 200$) it is sub-millisecond and feels instantaneous. Concrete medians will be measured during paper writing — see TODO note in MetricsPaperReference.md § 4.9.

`computeStressFromAPSP(nodes, apsp)` is a pure helper that consumes a (directed) APSP matrix and returns the symmetrised stress scalars. The same APSP is the prerequisite for **M11** (k-NN preservation) and **M12** (trustworthiness) in Stage 7; the helper exists so all three can share it once a within-modal cache lands.

Overlay: ❌ none in this iteration. A visualisation is planned (click a node → colour reachable nodes by symmetrised graph distance) — see `StressMetric.md` § "Visualisation".

CSV columns: `stress_per_pair`, `stress_unreachable_pairs`, `stress_reachable_pairs`.

### M2 — Crossing-Angle Metrics

`findCrossings(edges)` now attaches three fields to every `CrossingInfo`:

- `angle: number` — acute angle in radians, `arctan2(|cross|, |dot|)` of the two edge direction vectors. Folds into `[0, π/2]` regardless of source/target orientation.
- `edgeAType, edgeBType: string` — the two edges' Cytoscape `data('type')` values, **sorted lexicographically**, so `(HAS_VULN, LEADS_TO)` and `(LEADS_TO, HAS_VULN)` collapse into one bucket.

`computeCrossingAngleStats(crossings, tolRad = π/12)` returns `{ meanRad, minRad, rightAngleRatio }`. The right-angle window is **±15°** by default per Huang, Eades and Hong 2014.

CSV columns (degrees for human readability): `crossings_mean_angle_deg`, `crossings_min_angle_deg`, `crossings_right_angle_ratio`. JSON exports the same numeric values plus the dist below.

### M25 — Type-Pair Crossing Decomposition

`computeTypePairCrossingStats(crossings)` returns:

- `distribution: Record<string, number>` — `"typeA×typeB"` → count, with the pair sorted lex
- `topPairLabel: string` — most-frequent key (or `""` for empty input). Tie-break: lex-first key (deterministic for CSV stability).
- `topPairShare: number` — top-pair count / total crossings, ∈ `[0, 1]`

CSV columns: `crossings_top_pair_share`, `crossings_top_pair_label`. The label is RFC 4180-quoted when it contains a comma or double quote. The full per-pair distribution is **JSON-only** (variable cardinality) under `metrics.crossings_type_pair_distribution`.

### Crossings overlay coloring (M2 + M25 share the dot)

The Debug Overlay Settings modal exposes a **radio group** `Crossings — color dots by` — exactly one of the three modes is active at any time. M2 and M25 cannot both colour the dots simultaneously; they're alternative readings of the same overlay element. The user-facing scalars (M2 mean angle, M25 top pair) are computed and reported regardless of which colouring mode is selected — only the visual rendering depends on the radio:

- `none` — keep the stylesheet's default red (#ff2d55), back-compat with v0
- `angle` (M2) — interpolate `hsl(hue, 75%, 50%)` with hue ∈ `[0°, 120°]` mapped from angle ∈ `[0, π/2]` (red = acute → yellow ≈ 45° → green ≈ 90°)
- `typePair` (M25) — categorical 10-color palette assigned to each `typeA×typeB` bucket in descending count order (most-common pair = red, second = orange, …)

Implementation: `pickCrossingColor(c, mode, palette)` (`debugOverlay.ts:460`) and `buildTypePairPalette(crossings)` (`debugOverlay.ts:427`).

### M19 — Bridge Edge Proportion + Contraction Depth

PAGDrawer's visibility toggles (hide CWE / TI / etc.) replace chains of hidden nodes with a single "bridge" edge from the surviving predecessor to the surviving successor. Bridges carry a `chain_length` data attribute = the number of hidden nodes the bridge spans.

`chain_length` accumulates over chained `hideNodeType` calls. When CWE is hidden first, bridges CVE→TI get chain_length=1. When TI is hidden next, the new bridges CVE→VC get chain_length = (old CVE→TI chain_length, 1) + 1 (for TI itself) + (TI→VC chain_length, 0) = 2. The accumulation is implemented in `frontend/js/features/filter.ts` (`hideNodeType:142`) via the `readChainLength` helper at `filter.ts:32`.

`computeBridgeStats()` reports:
- `bridge_edge_proportion` — `|bridges| / |edges|`
- `mean_contraction_depth` — average `chain_length` across bridges only
- `bridge_edge_count` — raw count
- `bridge_chain_length_distribution` — JSON-only; e.g. `{ "1": 12, "2": 4 }`

CSV columns: `bridge_edge_proportion`, `mean_contraction_depth`, `bridge_edge_count`. Distribution dict is JSON-only.

Overlay: a per-bridge `k=N` label (font 11px, white with black outline) at the midpoint of every bridge whose chain_length > 0. Toggleable in the Debug Overlay Settings modal under "Reductions (M19 + M20)".

**Distribution shape — anchor-type property.** `chain_length` accumulates only across **consecutive** hidden types. Surviving types in the schema (`ATTACKER → HOST → CPE → CVE → CWE → TI → VC`) act as anchors that split a multi-type hide into independent runs. Hiding CPE+CWE+TI with CVE surviving yields a bimodal distribution: depth=1 bridges (HOST→CVE, CPE skipped) and depth=2 bridges (CVE→VC, CWE+TI skipped together). Length-3 bridges are structurally impossible in this case without also hiding CVE. The `bridge_chain_length_distribution` dict reflects this — expect multimodal histograms whenever a multi-layer hide straddles a surviving anchor type. See `MetricsPaperReference.md` § M19 for the worked nginx example.

### M20 — Edge Consolidation Ratio

For each compound parent (e.g. CVE_GROUP from outcomes-merge): how much edge consolidation did the merge achieve? `ECR = raw_edges / synthetic_edges` per parent, where:
- `raw_edges` = original edges connected to any child (counted regardless of `display: none` — that's the whole point: the originals were hidden by outcomes-merge)
- `synthetic_edges` = edges incident on the parent itself, marked `data('synthetic') === true`

`computeEcr()` aggregates as a **size-weighted mean** across parents that have synthetic edges (childCount-weighted). Compounds with no synthetic edges (e.g. prereqs-mode merge, ATTACKER_BOX) are excluded from the mean.

CSV columns: `mean_ecr_weighted`, `ecr_compounds_count`. Per-parent breakdown lives in JSON's `ecr_per_compound`.

Overlay: appends `(ECR×N.M)` to compound parent labels. Composes with M21's `(×N)`:
- M21 alone: `Outcome XYZ  (×5)`
- M20 alone: `Outcome XYZ  (ECR×3.4)`
- Both: `Outcome XYZ  (×5  ECR×3.4)` (or `Outcome XYZ (×5)  (ECR×3.4)` when the backend label already includes the count)

### M22 — Attribute Compression Ratio (CVE keys)

For a set of CVE nodes $V_{\mathrm{cve}}$ and a key function $k$:

$$
\mathrm{ACR}(k) = \frac{|\{ k(v) : v \in V_{\mathrm{cve}} \}|}{|V_{\mathrm{cve}}|} \in (0, 1]
$$

**ACR = 1** means every CVE has a unique key — no merge could compress them. **ACR → 0** means most CVEs collapse into the same bucket. The metric reports the **structural upper bound** on what the merge mechanism could achieve.

PAGDrawer reports two values, one per merge mode:
- `acr_cve_prereqs` — distinct prereq-keys / `|CVE|`
- `acr_cve_outcomes` — distinct outcome-keys / `|CVE|`
- `acr_cve_node_count` — denominator

The two values let a paper compare how compressible the same data is under each merge convention. A low `acr_cve_outcomes` (e.g. 0.32) and high `acr_cve_prereqs` (e.g. 0.68) on the same scan justifies "outcomes-merge for compression, prereqs-merge for grouping" framing.

**Implementation.** The merge-key functions live in `frontend/js/features/mergeKeys.ts` (`computePrereqKeyFromData:43`, `computeOutcomeKeyFromData:51`; live wrappers `computePrereqKey:68`, `computeOutcomeKey:77`), extracted from `cveMerge.ts` so the metric and the merge mechanism share the same key contract. The pure helper `computeAcrFromKeys(cveData)` (`metrics.ts:969`) takes plain `CveKeyData` records and returns the two ACRs in a single pass; the live `computeAcr()` (`metrics.ts:998`) walks `cy.nodes(':visible[type="CVE"]')` and delegates.

**Scope.** Computed over **visible** CVE nodes (excluding exploit-hidden), **including** CVEs currently inside a CVE_GROUP — they remain `:visible` (rendered as small dots inside the parent box). The metric measures structural compression potential across the visible set, regardless of merge state.

**Overlay.** ❌ none — ACR has no spatial location. CSV / JSON / modal only.

### M9 — Aspect Ratio

`computeAspectRatio(bb)` returns `min(w, h) / max(w, h) ∈ [0, 1]`. 1 = square; values approaching 0 = elongated. Returns 0 for null / zero-extent bboxes. CSV column: `aspect_ratio`. The Debug Overlay Settings modal toggles a `(AR = 0.42)` suffix on the bbox label.

### M21 — Compound Group Cardinality (generalised)

`computeCompoundCardinality()` aggregates visible non-debug nodes by their compound parent and reports:

- `largestGroupSize` — max children across all compound parents
- `singletonFraction` — parents with exactly one child / total parents
- `groupsCount` — total number of compound parents
- `sizeDistribution` — full size → count map for histogram display
- `groups` — per-parent `(parentId, size)` tuples for overlay rendering

**Note on `singletonFraction`:** the CVE-merge mechanism in `cveMerge.ts:176` skips groups with `< 2` members, so under normal operation `singletonFraction = 0`. The metric is preserved as a regression sentinel — a non-zero reading would surface immediately if a future merge mode produced singletons.

**The size-distribution dict is JSON-only.** CSV exports include `compound_groups_count`, `compound_largest_group_size`, and `compound_singleton_fraction` as scalars; the per-size dict would produce non-stable column headers between runs and is therefore omitted from CSV. JSON exports include the full `compound_size_distribution` object. The Statistics modal renders the dict as a `2×5  3×8  4×2`-style histogram row.

The overlay appends `(×N)` to every compound parent label. Idempotent: if a label already ends with `(×<digits>)` (e.g. CVE_GROUP from the data layer), the overlay leaves it untouched. Hiding the overlay restores all original labels via a saved-originals map.

CSV columns: `compound_groups_count`, `compound_largest_group_size`, `compound_singleton_fraction`.

---

## References

- **Purchase, H.C. (2002)** — "Metrics for Graph Drawing Aesthetics." *Journal of Visual Languages and Computing*, 13(5), 501–516.
- **Di Bartolomeo et al. (2024)** — "Evaluating Graph Layout Algorithms: A Systematic Review." *Computer Graphics Forum.* (Uses EL-CV alongside Purchase's metrics.)
- **greadability.js** — https://github.com/rpgove/greadability. Considered but not used; we only needed `crossing`, so a 40-line inline implementation was preferred.
