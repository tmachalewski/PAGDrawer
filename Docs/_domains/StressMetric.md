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

The exposed `directed` option on `computeAPSP` is `true` by default; passing `{ directed: false }` gives the undirected variant for callers that want it (e.g. a future Option-1 stress sub-metric, or M11/M12 on graphs where directionality isn't load-bearing).

### Reported scalars

| Field | Meaning |
|-------|---------|
| `stress_per_pair` | Mean of `(‖p_i − p_j‖_2 − d_ij)²` over reachable unordered pairs |
| `stress_unreachable_pairs` | Count of unordered pairs where `symmetrizedDistance` returned `undefined` |
| `stress_reachable_pairs` | Denominator of the mean — the number of pairs contributing to the sum |

The two pair counts together equal `C(|V|, 2)`, so a reader can recover the total pair count from either.

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

## Visualisation (planned)

Stress is a scalar, but its components are per-pair and easy to make visible:

- **Click a node.** Colour every reachable node by its symmetrised graph distance to the clicked node (red=close, green=far). The user can eyeball whether geometrically-close nodes are also topologically close — exactly what stress measures.
- **Click two nodes in sequence.** Show both directed distances numerically and the Euclidean distance for that pair. Useful for explaining the metric to readers.

Not yet implemented; tracked as a follow-up. The pure helpers (`computeAPSP`, `symmetrizedDistance`) are already in place, so the visualisation is a thin overlay layer on top of existing data.

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
