# Stress Metric (M1)

> The most-cited graph-drawing layout-quality metric. Reviewers expect it. PAGDrawer's implementation is **directed BFS + symmetrised distance** — read on for why.

For a quick API summary, see [`DrawingQualityMetrics.md`](DrawingQualityMetrics.md). This document explains the **semantic decisions** behind PAGDrawer's stress computation: what it measures, what it doesn't, and the directed-graph adaptation we ship.

---

## What stress measures

> **In one sentence:** how faithfully the on-screen distance between two nodes reflects the topological distance between them in the graph.

Formally, for a graph G = (V, E) drawn with node positions `p: V → ℝ²`, stress sums the squared difference between **layout distance** (Euclidean) and **graph distance** (shortest path) over all node pairs:

```
stress(G) = Σ over pairs (i, j) of (‖p_i − p_j‖_2 − d_ij)²
```

A perfect drawing — where every pair of nodes is geometrically as far apart as their topological distance — has stress 0. Any layout has stress > 0; smaller is better.

**Why it matters for the paper.** Stress is the canonical evaluation metric in the modern graph-drawing literature (Purchase 2002, Gansner-Koren-North 2004, Kamada-Kawai 1989, plus most stress-majorization-based layout algorithms). When a GD reviewer reads an evaluation table without a stress number, they assume the authors didn't run the standard battery. Including it is table stakes.

**Why it matters for PAGDrawer specifically.** Our reduction mechanisms (visibility toggles, CVE merging, exploit-paths) all transform the graph topology while keeping a layout (dagre) fixed. Stress quantifies how much each reduction *helps* or *hurts* the layout-faithfulness story: if hiding CWE/TI raises stress, the resulting graph displays poorly even if it has fewer crossings; if it lowers stress, the reduction genuinely simplifies the visual.

---

## The directed-graph problem

PAGDrawer's graph is a **layered DAG** (mostly):

```
ATTACKER → HOST → CPE → CVE → CWE → TI → VC
                              ↘ (back-edges via ENABLES)
```

Most node pairs have at most one directed path between them. For the pair (HOST, ATTACKER) there's no directed path either way; for (CVE, ATTACKER) there's a path back through HOST→ATTACKER's predecessor; for (CVE, VC) there's a single forward path.

This is awkward for the stress formula because **Euclidean distance is symmetric** (`‖p_i − p_j‖ = ‖p_j − p_i‖`) but **graph distance is not** (`d(A→B) ≠ d(B→A)` in general). Three plausible adaptations exist:

### Option 1 — Treat the graph as undirected

Symmetrise the adjacency: every directed edge becomes a bi-directional edge. Compute APSP on that. Use the result as `d_ij` directly.

**Pros:** Matches Purchase 2002's original convention. Simplest formula. Every pair in a connected graph has a defined distance.

**Cons:** Loses information. A drawing that places a CVE node geometrically close to its ENABLES-source CWE looks fine even though that's a structurally back-edged pair the directed structure says is "behind" the CVE. We're rewarding the wrong thing.

### Option 2 — Strict directed stress

Use the directed distance `d(i→j)`. Pairs with no directed path are reported as unreachable. Treat `(A, B)` and `(B, A)` as separate ordered pairs.

**Pros:** Honest to the directed structure. Disconnected pairs are explicit.

**Cons:** Most pairs in a layered DAG have a directed path in at most one direction. So 50%+ of pairs become "unreachable" and fall out of the average. The stress number is dominated by short forward chains. Comparable across graphs only if their reachability structures match — which is exactly what the reduction mechanisms change. So before/after numbers aren't comparable, defeating the purpose.

### Option 3 — Symmetrised: `min(d(i→j), d(j→i))`

Run **directed** BFS for the APSP matrix. For each unordered pair, use the shorter of the two directed paths; if neither exists, mark unreachable.

**Pros:** Still computes on the actual directed structure (so a back-edge that creates a short i→j path is reflected in d_ij). But every pair where *some* path exists in *some* direction contributes to the metric. Symmetric like Euclidean. Comparable before/after as long as reachability is preserved by the reduction.

**Cons:** Loses the asymmetry information for individual pairs. Two pairs where (i→j)=1 and (j→i)=∞ vs (i→j)=∞ and (j→i)=1 are treated identically. For PAGDrawer this is acceptable because layout is undirected (dagre lays out nodes in columns regardless of which way edges flow within a column).

---

## What PAGDrawer ships

**Option 3 — Directed BFS, symmetrised distance.** Specifically:

1. `computeAPSP(nodeIds, edges)` runs directed BFS from every node. The adjacency map only adds `source → target`, not the reverse. Result is `Map<sourceId, Map<targetId, distance>>`.
2. `symmetrizedDistance(apsp, a, b)` returns `min(d(a→b), d(b→a))`, or `undefined` when neither direction is reachable.
3. `computeStressFromAPSP(nodes, apsp)` iterates the upper triangle of pairs, calls `symmetrizedDistance` for each, and accumulates the squared difference against `‖p_i − p_j‖_2`. Unreachable pairs are excluded from the mean and reported separately.

The exposed `directed` option on `computeAPSP` is `true` by default; passing `{ directed: false }` gives the undirected variant for callers that want it (e.g. a future Option-1 stress sub-metric for comparison purposes). Stage 7's M11 (k-NN preservation) and M12 (trustworthiness) will reuse M1's APSP and therefore inherit the **directed** choice — they don't independently need an undirected variant.

### Reported scalars

| Field | Meaning |
|-------|---------|
| `stress_per_pair` | Mean of `(‖p_i − p_j‖_2 − d_ij)²` over reachable unordered pairs. **Raw** — has units of length² mixed with hop counts; not directly comparable across graphs of different sizes. |
| `stress_per_pair_normalized_edge` | Mean of `((‖p_i − p_j‖_2 / mean_edge_length) − d_ij)²`. Kamada-Kawai-style, dimensionless. The normalisation most cited in modern stress-majorization literature. |
| `stress_per_pair_normalized_diagonal` | Mean of `((‖p_i − p_j‖_2 / √(w² + h²)) − d_ij)²`. Layout distance scaled by the bounding-box diagonal — dimensionless, comparable across graphs of different drawing extents. |
| `stress_per_pair_normalized_area` | Mean of `((‖p_i − p_j‖_2 / √(w · h)) − d_ij)²`. Layout distance scaled by the geometric mean of the bbox sides (= `√drawing_area`). Dimensionless. |
| `stress_unreachable_pairs` | Count of unordered pairs where `symmetrizedDistance` returned `undefined` |
| `stress_reachable_pairs` | Denominator of the mean — the number of pairs contributing to the sum |

The two pair counts together equal `C(|V|, 2)`. The four stress values share the same APSP and pair structure — only the layout-distance scale factor differs.

### Why three normalisations

The raw `stress_per_pair` mixes Euclidean distance (in logical units, dependent on dagre's chosen scale) with graph distance (a dimensionless integer). Two graphs with identical structural quality but different bbox sizes produce wildly different raw stress values, making cross-graph comparison impossible.

Each normalised variant divides the layout distance by a length scale before the squared difference is taken, so both terms in `(layout_dist/scale − d_ij)` are dimensionless and the result is comparable across graphs.

| Normalisation | Scale | Story it tells |
|---------------|-------|----------------|
| `_normalized_edge` | `mean_edge_length` (intrinsic to the graph) | "If every edge were unit-length, how off would each pair be?" Robust to bbox-size noise. Standard KK convention. |
| `_normalized_diagonal` | `√(w² + h²)` (corner-to-corner) | "What fraction of the drawing's extent does the per-pair error span?" Captures the actual visible footprint. |
| `_normalized_area` | `√(w · h)` (geometric mean of sides) | "What fraction of the average side length does the per-pair error span?" Less sensitive to extreme aspect ratios than the diagonal. |

For paper purposes the recommendation is to report `_normalized_edge` (most-cited) but include `_normalized_diagonal` and the raw value as alternatives in the appendix; reviewers comfortable with different normalisation conventions can cross-check. PAGDrawer ships all three so the choice can be made at write-up time, not at compute time.

Implementation note: `computeStressFromAPSP(nodes, apsp, layoutScale)` accepts the scale as an optional argument (default `1`, which is the raw stress). `computeStress()` runs the function four times against a single APSP matrix — each evaluation is O(|V|²), so the total cost is well within the modal's open-time budget.

---

## Why BFS, not Dijkstra / Bellman-Ford / Floyd-Warshall

PAGDrawer's edges are **unweighted** — each edge has unit cost. For unweighted graphs, BFS computes single-source shortest paths in `O(|V| + |E|)`, optimal.

| Algorithm | Best fit | Cost on our input |
|-----------|----------|-------------------|
| **BFS** | unweighted | `O(|V|·(|V| + |E|))` |
| Dijkstra | non-negative weights | `O(|V|·(|E| + |V| log|V|))` — heap overhead is wasted on unit weights |
| Bellman-Ford | negative weights allowed | `O(|V|² · |E|)` — strictly worse here |
| Floyd-Warshall | dense graphs | `O(|V|³)` — much worse for sparse PAGDrawer graphs |

So BFS isn't a "simpler-but-less-correct" choice; it's **the** correct algorithm for the input shape. Naming things after Dijkstra/Floyd-Warshall would suggest weighted-graph machinery that this metric does not need.

---

## Behaviour with compound nodes (CVE merge, ATTACKER_BOX)

PAGDrawer's `merge by outcomes` and `merge by prerequisites` features create CVE_GROUP compound parents that wrap the merged CVEs. ATTACKER_BOX does the same for the initial-state VCs.

**As of 2026-05-05** stress operates on `getStressEligibleNodes()` — visible non-debug nodes that have at least one **visible** incident edge. This filter cleanly handles compound merging:

| Mode | Compound parent | Compound children | Filter outcome |
|------|-----------------|-------------------|----------------|
| **outcomes merge** | Has synthetic edges → kept | Original edges are `display: none` → no visible edges → **filtered out** | Stress sees compound parents + non-merged nodes; correct |
| **prereqs merge** | No synthetic edges → **filtered out** | Original edges remain visible → kept | Stress sees children + non-merged; correct |
| **ATTACKER_BOX** | No edges itself → **filtered out** | VCs have HAS_STATE edges → kept | Correct; ATTACKER (separate from ATTACKER_BOX) is also always visible and connected |

**Net effect.** `stress_unreachable_pairs` no longer inflates structurally after merge. It reflects only genuine topology gaps (e.g. a CVE truly unreachable from any VC because the data has no path). When comparing stress across reduction steps in the paper, prefer the **normalised** values (`*_normalized_edge` / `_diagonal` / `_area`) and report `stress_reachable_pairs` alongside so the reader can see the denominator changing.

**Implementation.** `getStressEligibleNodes()` lives next to `getVisibleNodesWithIds()` in `frontend/js/features/metrics.ts`; the latter is preserved for callers that want the broader set (bbox computation, etc.). M11 and M12 in Stage 7 will share the same eligibility filter.

**Historical note.** Before the visible-edge filter, stress included compound parents *and* their children regardless of edge visibility — outcomes-merge would inflate `stress_unreachable_pairs` by `|merged children| · (|V| − |merged children|)`. The reachable-pair stress was correct; only the side counter was noisy. The filter resolves both. When reading old JSON exports (pre-2026-05-05), expect higher unreachable counts after the merge step.

---

## Edge cases and the "skip-and-report" convention

Per `metric_proposals.md` the disconnected-graph convention is **skip-and-report**: unreachable pairs do not contribute to the mean (which would otherwise require an arbitrary "infinite distance" choice that distorts the number), but their count is exposed alongside the metric so they can't be silently swallowed.

Why pairs become unreachable in PAGDrawer:

- **Visibility toggles.** Hiding CWE+TI breaks the chain CVE→VC. Pairs across the break become unreachable in directed mode, but most still have a directed path through the bridge edges that get inserted.
- **Exploit-paths mode.** Hides nodes outside selected attack chains; pairs spanning hidden regions become unreachable.
- **Filtered scans.** Multiple scans with no shared CPE produce two effectively-disconnected sub-graphs even though both are visible.

The unreachable count is reported in:

- The CSV: column `stress_unreachable_pairs`
- The JSON: `metrics.stress_unreachable_pairs`
- The Statistics modal: appended to the stress row, e.g. `12.50  (87 pairs, 3 unreachable)`

---

## Complexity and performance

`O(|V| · (|V| + |E|))` for the APSP, `O(|V|²)` for the pair iteration. Total `O(|V|² + |V|·|E|)`.

| Graph size | APSP cost (rough) |
|-----------|-------------------|
| ~70 nodes / ~90 edges (typical PAGDrawer) | microseconds |
| ~300 nodes / ~600 edges | < 50 ms |
| ~1000 nodes / ~3000 edges | ~ 1 second on the main thread |

Stress is computed lazily — only when the Statistics modal opens or refreshes — so even at the upper end the user-perceived cost is at most a single sub-second beat after clicking 📊.

If a future scan ever pushes stress compute above ~1 second consistently, the right fix is a within-modal cache: `computeMetrics()` would memoize the APSP map by `(visibleNodeIds, visibleEdgeIds)` so subsequent reads (export, JSON, hint hover) reuse the matrix. **M11 (k-NN preservation)** and **M12 (trustworthiness)** in Stage 7 will need the same APSP matrix and benefit from the same cache.

---

## Visualisation

Stress is a scalar, but its components are per-pair and easy to make visible. Two modes available in the **Debug Overlay Settings** modal under "Stress visualisation (M1)":

### Mode 1 — Color nodes by graph distance from clicked source

When the toggle is on, **clicking any node** sets it as the source and recolours every other visible node by symmetrised graph distance:

- **Source node** — black fill with a yellow border, can't be missed
- **Reachable, distance d (1 ≤ d ≤ d_max)** — `hsl((d/d_max)·120°, 75%, 55%)` interpolating red (closest) → yellow → green (farthest)
- **Unreachable** — translucent grey

If the layout is faithful, geometrically-close nodes will also be coloured red. A node that's coloured red but visually far from the source — or coloured green but visually close — is a layout fidelity issue this mode lets you spot at a glance. Background-clicking dismisses the colouring; clicking a different node moves the source.

### Mode 2 — Show pair distances on click

When the toggle is on, **clicking two nodes in sequence** pops a floating panel in the upper-right of the viewport showing:

- **From / To** — the two clicked node IDs
- **d(from → to)** — directed distance, or "unreachable"
- **d(to → from)** — reverse directed distance, or "unreachable"
- **symmetrised** — the value the metric uses (= `min` of the two)
- **Euclidean** — `‖p_from − p_to‖_layout`

A third click resets to "first selected"; the panel can also be dismissed via its `×` button or by clicking the graph background.

Both modes can be enabled simultaneously — a single click triggers both behaviors. The pure helpers `computeDistanceColoringStyles(sourceId, nodes, apsp)` and `computeStressPairDisplay(firstId, secondId, nodes, apsp)` live in `frontend/js/ui/debugOverlay.ts` and are unit-tested independently of Cytoscape.

---

## What this metric does NOT do

- **Not a ranking metric.** It's a continuous value; comparing two graphs by raw stress only makes sense if their |V| and reachability structure are similar. Always report `stress_reachable_pairs` alongside.
- **Not weighted by node-pair semantics.** Two layered nodes 1 hop apart contribute the same as a back-edge pair 1 hop apart — the metric doesn't know which pair "matters more" for analyst tasks. (`metric_proposals.md` § M14 discusses an information-preserving alternative.)
- **Not a substitute for human evaluation.** Stress correlates with path-tracing performance (Ware-Purchase-Colpoys-McGill 2002) but is not a proxy for it. The paper's user-study limitation paragraph should acknowledge this.

---

## References

- **Purchase, H.C. (2002)** — "Metrics for Graph Drawing Aesthetics." *Journal of Visual Languages and Computing*, 13(5), 501–516. The classical formulation, undirected.
- **Kamada, T. and Kawai, S. (1989)** — "An algorithm for drawing general undirected graphs." *Information Processing Letters*, 31(1), 7–15. Original stress-minimisation layout.
- **Gansner, E.R., Koren, Y. and North, S. (2004)** — "Graph Drawing by Stress Majorization." *International Symposium on Graph Drawing*. Modern stress-based layout, with the per-pair-normalised formulation we follow.
- **Ware, C., Purchase, H.C., Colpoys, L. and McGill, M. (2002)** — "Cognitive measurements of graph aesthetics." *Information Visualization*, 1(2), 103–110. Empirical link between stress-like metrics and path-tracing performance.

---

## Implementation pointers

| File | Role |
|------|------|
| `frontend/js/features/metrics.ts` | `computeAPSP`, `symmetrizedDistance`, `computeStressFromAPSP`, `computeStress` |
| `frontend/js/features/metrics.test.ts` | Pure-function tests for all four (directed + undirected APSP, symmetrise edge cases, stress upper-triangle iteration, skip-and-report) |
| `frontend/js/ui/statistics.ts` | Surfaces `Stress per pair (M1)` row in the Drawing Quality table |
| `Docs/_domains/DrawingQualityMetrics.md` | API summary table |
