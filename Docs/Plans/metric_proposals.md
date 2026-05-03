# Metric Proposals for the GD 2026 Submission

This document collects candidate metrics you could compute alongside the ten the Statistics modal already exports per snapshot: `nodes`, `edges`, `unique_cves`, `trivy_vuln_count`, `crossings_raw`, `crossings_normalized` (Purchase 2002), `crossings_per_edge` ($C/E$), `drawing_area`, `area_per_node` ($A/N$), and `edge_length_cv` ($\mathrm{CV}_\ell$). Each entry gives the formal definition, a computation algorithm, asymptotic complexity, the original source, and a note on which of your three mechanisms it most directly speaks to. Pick the ones that strengthen your story; keep the rest in an appendix as a richer characterisation of the layouts.

I have organised the metrics into six families: layout-aesthetic metrics that the graph-drawing community has used for decades, distance-and-topology preservation metrics from the MDS / dimension-reduction tradition, information-preservation metrics that match the soundness invariants in your propositions, mechanism-specific metrics you would essentially own, type-aware metrics that exploit your heterogeneous-DAG abstraction, and visual-density/clutter metrics that bridge the objective and the perceptual.

---

## Implementation Notes (Shared Data Structures)

Before computing any metric, prepare these once per layout snapshot:

1. **Layout coordinates** as an $|V| \times 2$ array `pos[v]` of $(x, y)$ pairs, in the logical coordinate system used by Cytoscape.js (invariant under viewport zoom and pan).
2. **Type assignment** `type[v]` and **edge type** `etype(u, v) = (type[u], type[v])`.
3. **All-pairs shortest path matrix** `D[i][j]` via BFS from each node (unweighted) or Dijkstra (weighted). Cost: $O(|V|(|V|+|E|))$. Used by M1 (stress), M11 (NP), M12 (T&C), M15 (path-length preservation), M13 (shape-based, partially).
4. **Edge-segment intersection list** $X = \{(e_1, e_2)\}$ with the intersection point for each. Compute via Bentley-Ottmann sweep (`shapely` in Python or a custom segment-intersection routine). Cost: $O((|E|+|X|)\log |E|)$. Used by M2 (crossing angle), M25 (type-pair decomposition).
5. **Bridge-edge provenance**: for each bridge edge $e \in E_{\mathrm{bridge}}$, store the contracted chain $w_0, w_1, \dots, w_k$ in $G$ that the bridge replaces. Built as a side-effect of the bridge-edge algorithm in the paper (Mechanism 2). Used by M19 (bridge-edge proportion and contraction depth), M15 (path-length preservation).
6. **Compound parent membership**: for each compound parent $p_j$, the list of child nodes $G_j$. Built by the compound-merging algorithm in the paper (Mechanism 3). Used by M16 (typed out-signature preservation), M20 (edge consolidation ratio), M21 (group cardinality), M22 (attribute compression ratio).
7. **Disconnected-graph convention**: After Step 3 (exploit-paths-only filter) the graph may be disconnected. Decide a convention up front for $D[i][j]$ when no path exists: use $\infty$ (and exclude such pairs from sums) or use a finite cap (e.g., diameter + 1). All metrics that consume $D$ inherit this choice. We recommend the $\infty$-and-exclude convention because the cap conflates "unreachable" with "very far," which is semantically wrong for an attack graph.

**On segment intersection.** For your graph sizes (under ~6{,}000 edges) brute-force pairwise segment intersection in $O(|E|^2)$ is fast enough and simpler to implement than Bentley-Ottmann. In Python, `shapely.geometry.LineString` plus `shapely.STRtree` for spatial pruning gets you to roughly $O(|E| \cdot \log |E|)$ in practice with a few lines of code. Reserve a true sweep-line implementation for graphs above $\sim 100{,}000$ edges. The output should be a list of triples `(e1, e2, point)` and you should preserve the edge-type pair `(\tau_E(e_1), \tau_E(e_2))` alongside it for M25.

For polyline-rendered edges (Cytoscape.js with bend points), treat each polyline as a sequence of straight segments and compute crossings between segments rather than between endpoint-to-endpoint chords. The dagre default in your prototype uses straight-line edges, so endpoint-to-endpoint is correct as long as you do not switch renderers.

---

## Statistical Reporting Convention

The evaluation runs across $\sim 7$ Docker images $\times$ $6$ reduction steps = $42$ (graph, step) cells per metric. Some metrics will be noisy across images (their value depends as much on the underlying graph as on the reduction). Decide a convention up front and apply it uniformly:

- **Per-step aggregation across images**: report **mean ± std** across the image corpus per (step, metric) cell. Be aware that scans range from $\sim 60$ to $\sim 830$ nodes, so a single outlier image can pull the mean noticeably; flag any cell where one image is more than $2\sigma$ from the mean and discuss it in prose.
- **Per-image trajectories**: when reporting a single image's progression across steps, plot the raw values; they are not statistical samples and don't need error bars.
- **For metrics expected to be $\sim$constant across reduction steps** (the empirical-validation metrics M14, M15, M16): report whether the value is exactly $1$ for every cell. If not, table the deviations explicitly.

Each metric definition below ends with a "Reporting" line indicating whether per-image-spread reporting matters; absence of that line means the metric varies enough between images that mean ± std is the default. Mechanism-specific metrics (M19–M23) are particularly noisy across images because they depend on the input scan's structure (attribute homogeneity, chain depth, type distribution) — call those out explicitly.

---

## Family 1: Layout-Aesthetic Metrics

These measure intrinsic qualities of the drawing, independent of the graph's semantic structure. Most have been validated through controlled human studies; the canonical reference set is [Purchase 1997 "Which Aesthetic has the Greatest Effect on Human Understanding?"](https://consensus.app/papers/details/7bff0d94671c5958b6117cc76388c7e1/?utm_source=claude_desktop) (643 citations) and [Purchase 2002 "Metrics for Graph Drawing Aesthetics"](https://consensus.app/papers/details/dfb363e909f9532a91fa2172dd65a7e2/?utm_source=claude_desktop) (328 citations), which gives normalised formulas for seven core aesthetics.

### M1. Stress

The single most-cited non-crossing layout-quality metric. Stress measures whether geometric distance in the drawing is proportional to graph-theoretic distance.

**Formula.** Let $d_{ij}$ be the graph-theoretic shortest-path distance between nodes $i$ and $j$, $\|p_i - p_j\|$ the Euclidean distance in the drawing, and $w_{ij}$ a weight (commonly $w_{ij} = 1/d_{ij}^2$ to balance contributions across distance scales):

$$\mathrm{stress}(P) = \sum_{i < j} w_{ij} \, (\|p_i - p_j\| - d_{ij})^2$$

**Algorithm.**
1. Compute all-pairs shortest paths $d_{ij}$ via BFS from each node (unweighted graph) or Dijkstra (weighted), $O(|V|(|V| + |E|))$.
2. For each pair $(i, j)$ with $d_{ij} < \infty$, compute $\|p_i - p_j\|$ from layout coordinates.
3. Sum the weighted squared residuals over reachable pairs only; report the count of unreachable pairs separately.

**Disconnected-graph caveat.** After Step 3 (exploit-paths-only filter) some node pairs are no longer connected. The standard convention is to skip such pairs in the stress sum and report the count of skipped pairs alongside the stress value, since both affect comparability. An alternative is to use a finite cap (e.g., $d_{ij} = \mathrm{diam}(G) + 1$ for unreachable pairs) but this conflates "unreachable" with "very far," which is misleading for an attack graph.

**Complexity.** $O(|V|(|V|+|E|))$ for APSP plus $O(|V|^2)$ for the sum. For your graph sizes (60–830 nodes) this is trivial. For larger graphs use the low-rank approximation in [Khoury et al. 2012](https://consensus.app/papers/details/8fe2e76425d859a8b81e184e8c745a89/?utm_source=claude_desktop), which costs $O(k|V|+|V|\log |V|+|E|)$ per iteration.

**Source.** Introduced by Kamada and Kawai (1989) as the energy function of their force-directed algorithm. The modern computational treatment is [Gansner, Koren and North, "Graph Drawing by Stress Majorization", GD 2004](https://consensus.app/papers/details/b2f5a4dbd7fc5e0e81da68bc75b3268b/?utm_source=claude_desktop). For the perceptual interpretation see [Mooney et al. 2024 "The Perception of Stress in Graph Drawings"](https://consensus.app/papers/details/2b6c0dc1e39256248d1e5d4ce0949e2e/?utm_source=claude_desktop).

**Why relevant.** Reports whether your layered layout is faithful to graph topology. Layered layouts will have higher stress than force-directed because layers force coordinates; that is an honest report and worth the discussion. The key question is whether your reductions improve stress (preserve topology better) or worsen it (compound parents distort distances). I expect mixed results worth analysing.

**What "good" looks like.** Lower is better. Stress per *summed* pair (i.e., divided by the number of pairs actually included in the sum, not $\binom{|V|}{2}$) is the size-normalised variant; report this for cross-graph comparison along with the count of excluded unreachable pairs. Using $\binom{|V|}{2}$ as the denominator would deflate the score on disconnected graphs.

**Reporting.** Mean ± std across images per step. The size-normalised per-pair variant is mandatory for cross-image aggregation; raw stress is dominated by graph size and not comparable.

---

### M2. Crossing-Angle Metrics

A complement to your $C/E$ that perceptual studies show matters as much as crossing count itself.

**Formulas.** For each pair of crossing edges $e_1, e_2$, compute the angle $\theta(e_1, e_2) \in (0, \pi/2]$ between them at the crossing point. Three derived metrics:

- Mean crossing angle: $\bar\theta = \frac{1}{|X|} \sum_{(e_1,e_2) \in X} \theta(e_1, e_2)$
- Minimum crossing angle (crossing-angle resolution): $\theta_{\min} = \min_{(e_1,e_2) \in X} \theta(e_1, e_2)$
- Right-angle ratio: $\rho_{\mathrm{RAC}} = |\{(e_1,e_2) \in X : \theta(e_1,e_2) > \pi/2 - \tau\}| / |X|$ for a tolerance $\tau$ (commonly $\tau = \pi/12 = 15°$)

where $X$ is the set of crossing edge pairs.

**Algorithm.** Compute crossings via segment-intersection (Bentley-Ottmann gives $O((|E|+|X|)\log |E|)$). For each crossing edge pair, treat each edge as a direction vector $\vec{e_i} = p_{\mathrm{tgt}(e_i)} - p_{\mathrm{src}(e_i)}$ and compute the acute angle between the two lines:

$$\theta(e_1, e_2) = \arctan_2\!\Big(|\vec{e_1} \times \vec{e_2}|, \, |\vec{e_1} \cdot \vec{e_2}|\Big)$$

The absolute value on both arguments folds the result into $[0, \pi/2]$ regardless of edge orientation. (In 2D, the cross product $\vec{e_1} \times \vec{e_2}$ is the scalar $e_{1x}e_{2y} - e_{1y}e_{2x}$.)

**Complexity.** $O((|E|+|X|)\log |E|)$ to detect crossings plus $O(|X|)$ for angles.

**Source.** [Huang, Eades and Hong 2014 "Larger crossing angles make graphs easier to read"](https://consensus.app/papers/details/f83e52e93715565eab6519f0062f7d32/?utm_source=claude_desktop) demonstrates the perceptual effect with two controlled studies, and identifies "minimum crossing angle on the path" as the single best aesthetic measure when path finding is the task. The earlier [Huang 2007 eye-tracking study](https://consensus.app/papers/details/a33b29c030795891ace981ab9652e73b/?utm_source=claude_desktop) is the original empirical motivation. The survey [Didimo, Eades and Liotta 2013](https://consensus.app/papers/details/969658f9042d5ceaa7aab24e74680e02/?utm_source=claude_desktop) covers algorithmic results.

**Why relevant.** Path-tracing is the canonical attack-graph analyst task. Even where your reductions leave crossings, they may have become more orthogonal as the layout breathes. Reporting mean crossing angle (and the minimum) tells the full story alongside $C/E$.

**What "good" looks like.** Higher mean is better; closer to $\pi/2$ is the ideal. Right-angle ratio above ~70% is considered good.

**Reporting.** Mean ± std across images per step for the mean angle; report the *minimum* angle (across the corpus) separately rather than aggregating it — a single very-acute crossing matters more than the average.

---

### M3. Angular Resolution at Nodes

The angular counterpart to crossing angle, measured at node-edge incidences rather than at crossings.

**Formula.** For a node $v$ with $k$ incident edges (in- and out- combined, treated as undirected for this metric), sort the $k$ outgoing-direction angles $\beta_1 \le \beta_2 \le \dots \le \beta_k$ around $v$ in $[0, 2\pi)$. The $k$ cyclic angular gaps are $\alpha_i = \beta_{i+1} - \beta_i$ for $i < k$, and $\alpha_k = 2\pi - \beta_k + \beta_1$ (the wrap-around). Take the minimum:

$$\mathrm{ang\_res}(v) = \min_i \alpha_i, \quad \mathrm{AR}(G) = \min_{v \in V} \mathrm{ang\_res}(v)$$

A normalised variant divides each $\alpha_i$ by the optimal $2\pi/k$ before taking the min, giving values in $[0, 1]$.

**Algorithm.** For each node $v$ and each incident edge $(v, u)$ (or $(u, v)$), compute angle $\beta = \arctan_2(p_{u,y} - p_{v,y}, p_{u,x} - p_{v,x})$. Sort. Take cyclic consecutive differences. Return the min.

**Complexity.** $O(|V| + |E| \log \Delta)$ where $\Delta$ is maximum degree.

**Source.** Standard graph-drawing aesthetic from the 1990s. Combined with crossing angle in [Argyriou et al. 2010 "Maximizing the Total Resolution of Graphs"](https://consensus.app/papers/details/71be2d8b6cff599cb8db32006d96ed30/?utm_source=claude_desktop). The "total resolution" is the minimum of angular resolution and crossing angle, a useful single number.

**Why relevant.** Compound merging often reduces a node's in-degree and out-degree (because edges are consolidated), which should improve angular resolution at the surviving nodes. Worth verifying.

---

### M4. Edge Orthogonality

Measures alignment of edges with the canonical horizontal and vertical axes. Especially relevant for layered layouts where you want edges to flow cleanly between layers.

**Formula.** Compute each edge's geometric angle $\phi_e \in [0, 2\pi)$ via $\arctan_2$, then fold into $[0, \pi/2)$ by $\theta_e = \phi_e \bmod (\pi/2)$. The folded angle $\theta_e$ is the edge's angle from the horizontal axis modulo a quarter turn; the *distance to the nearest axis* (horizontal or vertical) is $\min(\theta_e, \pi/2 - \theta_e) \in [0, \pi/4]$, with $0$ meaning axis-aligned and $\pi/4$ meaning diagonal. Define:

$$\mathrm{orth}(e) = 1 - \frac{\min(\theta_e, \pi/2 - \theta_e)}{\pi/4}$$

Aggregate: $\mathrm{ORTH}(G) = \frac{1}{|E|}\sum_e \mathrm{orth}(e)$, in $[0,1]$ where 1 is perfectly orthogonal (axis-aligned) and 0 is at 45°.

**Algorithm.** For each edge with endpoints $p_u, p_v$, compute $\phi = \arctan_2(p_{v,y} - p_{u,y}, p_{v,x} - p_{u,x})$, fold $\theta = \phi \bmod (\pi/2)$, take $\min(\theta, \pi/2 - \theta) \in [0, \pi/4]$, normalise.

**Complexity.** $O(|E|)$.

**Source.** Defined formally in [Purchase 2002 "Metrics for Graph Drawing Aesthetics"](https://consensus.app/papers/details/dfb363e909f9532a91fa2172dd65a7e2/?utm_source=claude_desktop). The recent [Mooney et al. 2024](https://consensus.app/papers/details/0d8758af083a5ada8c614a5f32cfc2e7/?utm_source=claude_desktop) "Multi-Dimensional Landscape of Graph Drawing Metrics" includes it in their ten-metric panel.

**Why relevant.** Bridge edges in your layer-hiding mechanism span longer geometric distances than the original edges they replace. Whether they remain orthogonal or become diagonal lines that cut across the layout is a real readability concern.

---

### M5. Edge Length Uniformity (Coefficient of Variation)

You already report this as $\mathrm{CV}_\ell$. For completeness:

**Formula.** $\mathrm{CV}_\ell = \sigma_\ell / \mu_\ell$ where $\mu_\ell$ and $\sigma_\ell$ are the mean and standard deviation of edge lengths.

**Source.** [Fruchterman and Reingold 1991 "Graph Drawing by Force-directed Placement"](https://en.wikipedia.org/wiki/Force-directed_graph_drawing) (cited in your bibliography as `fruchterman1991`) introduced uniform edge length as an aesthetic. [Di Battista et al. 1999 "Graph Drawing"](https://en.wikipedia.org/wiki/Graph_drawing) is the textbook reference.

**Note.** This metric can mislead in your case: bridge edges contract several hops into one, so the resulting bridge edges are systematically *longer* than retained edges, which inflates $\mathrm{CV}_\ell$ even though the layout is still readable. Consider reporting **per-edge-type** edge length CV separately, so the bridge contribution is visible but doesn't pollute the global metric.

---

### M6. Symmetry Score

Quantifies how much axial, rotational, or translational symmetry the drawing exhibits.

**Formula sketch.** The Klapaukh, Marshall and Pearce 2018 metric checks for each pair of edges whether their reflections across a candidate axis match other edges in the drawing, weighted by edge length. Welch and Kobourov 2017 propose a stress-based variant.

**Algorithm.** For axial symmetry across an axis $a$: reflect each node $p_i$ across $a$ to get $p'_i$; for each edge $(p_i, p_j)$ find the reflected partner $(p'_i, p'_j)$; score is the fraction of edges with a matching reflected partner. Repeat over a sample of candidate axes (e.g., centroid plus principal-axis directions). Take the maximum.

**Complexity.** $O(|E|^2)$ per axis with naive matching, $O(|E| \log |E|)$ with hashing of edge endpoints. Computing axial and rotational symmetry in $O(|V|\log|V|)$ is achieved by [Meidiana et al. 2020 "Quality Metrics for Symmetric Graph Drawings"](https://consensus.app/papers/details/ddd76edf521e50bc808554dd4048a2ec/?utm_source=claude_desktop) using group-theoretic methods.

**Source.** The foundational work is [Welch and Kobourov 2017 "Measuring Symmetry in Drawings of Graphs"](https://consensus.app/papers/details/730e7f78b2e75ac5b4eada4c0b4477e7/?utm_source=claude_desktop). The most recent is [Meidiana, Hong, Eades et al. 2022 "Automorphism Faithfulness Metrics for Symmetric Graph Drawings"](https://consensus.app/papers/details/027d408e736f5e0684e66fcf47e86d14/?utm_source=claude_desktop), which compares the layout's geometric symmetries against the graph's automorphism group.

**Why relevant.** Compound merging tends to produce visually symmetric clusters when the underlying ordinal-attribute distribution is symmetric across hosts. Reporting symmetry would surface this.

**Why you might skip.** Symmetry tends to be marginal for layered DAGs because the layer structure breaks most natural symmetries. If you've shown your layout doesn't optimise for it, this metric won't move much. Skip unless you find a concrete reason to discuss.

---

### M7. Edge Continuity

Measures how straight a multi-edge path stays at each intermediate node. Cited by [Ware, Purchase, Colpoys and McGill 2002 "Cognitive Measurements of Graph Aesthetics"](https://consensus.app/papers/details/f90732290c375b9589d8c00b78fda373/?utm_source=claude_desktop) (404 citations) as one of the two most important factors for path-tracing, alongside path length, surpassing edge crossings.

**Formula.** For each path-internal node $v$ on a path $u \to v \to w$, define the deviation angle $\delta(u, v, w) = \pi - \angle(u, v, w)$ (where $\angle$ is the angle at $v$ between the two edges). A continuity-respecting path keeps $\delta$ small at every intermediate node.

To use as a layout metric, average over all 2-paths in the graph:

$$\mathrm{CONT}(G) = 1 - \frac{1}{|2\text{-paths}|}\sum_{(u,v,w)} \frac{\delta(u,v,w)}{\pi}$$

**Algorithm.** Enumerate all 2-paths in the graph (directed), compute the angle at the middle vertex, average.

**Complexity.** $O(\sum_v \deg(v)^2)$ which is $O(|V| \cdot \Delta^2)$ in the worst case.

**Source.** [Ware et al. 2002 "Cognitive Measurements of Graph Aesthetics"](https://consensus.app/papers/details/f90732290c375b9589d8c00b78fda373/?utm_source=claude_desktop) is the empirical foundation; introduces continuity as an under-appreciated aesthetic.

**Why relevant.** Bridge edges that span several layers may zig-zag through node centres at the contracted endpoints, which reduces continuity even when crossings are absent. This is a precise way to measure "does the simplified graph still let me trace a path with my eye in one motion."

---

### M8. Bounding Box Compactness

Measures how efficiently the drawing uses its bounding box. You currently report drawing area per node ($A/N$); this is the inverse complement.

**Formula.** Let $A_{\mathrm{bbox}}$ be the area of the layout's bounding box and $A_{\mathrm{ink}}$ be the total area "occupied" by nodes (sum of node areas) and edges (sum of edge widths times lengths). Compactness:

$$\mathrm{COMP}(G) = \frac{A_{\mathrm{ink}}}{A_{\mathrm{bbox}}}$$

A normalised variant uses the convex hull of node positions instead of the bounding box.

**Algorithm.** Compute bounding-box (or convex hull) area; sum node areas and edge "ink" (length times rendering width); divide.

**Complexity.** $O(|V|+|E|)$ for bbox, $O(|V|\log|V|)$ for convex hull.

**Source.** Tufte's "data-ink ratio" idea from "The Visual Display of Quantitative Information" (1983); applied to graph drawing aesthetics in the [Mooney et al. 2024](https://consensus.app/papers/details/0d8758af083a5ada8c614a5f32cfc2e7/?utm_source=claude_desktop) ten-metric panel.

**Why relevant.** A more interpretable replacement for $A/N$ that doesn't go the "wrong way" when the dagre layout spaces fewer nodes apart (your current postgres/redis problem). I recommend swapping $A/N$ for compactness in v3 of the paper.

---

### M9. Aspect Ratio

Quality is highest when the layout fits a screen-typical 4:3 or 16:9 ratio.

**Formula.** $\mathrm{AR}(G) = \min(w, h) / \max(w, h)$ where $w, h$ are the bounding-box width and height. AR $\in (0, 1]$, with $1$ being a square.

**Algorithm.** Trivial.

**Source.** [Purchase 2002](https://consensus.app/papers/details/dfb363e909f9532a91fa2172dd65a7e2/?utm_source=claude_desktop). [Mooney et al. 2024](https://consensus.app/papers/details/0d8758af083a5ada8c614a5f32cfc2e7/?utm_source=claude_desktop) reports normalised distributions across many graphs.

**Why relevant.** Layered layouts often produce extremely wide-and-short or tall-and-narrow drawings. As your reductions remove nodes, the aspect ratio should improve. Report it.

---

### M10. Total Edge Length

A simple aesthetic preferred by force-directed layouts. Reported as a sanity check more than a contribution.

**Formula.** $\mathrm{TEL}(G) = \sum_{e \in E} \|e\|$.

**Algorithm.** Sum edge lengths.

**Complexity.** $O(|E|)$.

**Why relevant.** As your reductions consolidate edges, total length should drop substantially. Worth reporting alongside $E$ to show the visual ink reduction directly.

---

## Family 2: Distance and Topology Preservation Metrics

These come from the dimension-reduction tradition (multi-dimensional scaling, t-SNE, UMAP) where the question is "does the low-dimensional embedding preserve the high-dimensional structure?" Translated to graph drawing: does the 2D layout preserve graph-theoretic structure?

### M11. Neighborhood Preservation (k-NN Trust)

Measures whether nodes that are close in the drawing are also close in the graph.

**Formula.** For each node $v$, let $N_k^G(v)$ be its $k$ nearest neighbours by graph distance and $N_k^L(v)$ by layout distance. Define:

$$\mathrm{NP}_k(G) = \frac{1}{|V|}\sum_{v \in V} \frac{|N_k^G(v) \cap N_k^L(v)|}{k}$$

**Algorithm.**
1. Compute APSP (already needed for stress).
2. For each $v$, get top-$k$ graph neighbours $N_k^G(v)$ as the $k$ nodes with smallest *finite* $D[v][\cdot]$ (skip unreachable nodes), and top-$k$ layout neighbours $N_k^L(v)$ as the $k$ nodes with smallest Euclidean distance from $p_v$.
3. Compute the size of the intersection divided by $k$; this is the per-node k-NN overlap (also called k-NN precision, since $|N_k^G| = |N_k^L| = k$ makes precision and recall equal).
4. Average across all nodes that have at least $k$ reachable neighbours; report the count of excluded nodes if any.

Note: this is k-NN overlap, not Jaccard similarity. Jaccard would divide by $|N_k^G \cup N_k^L|$ rather than $k$; the two coincide only when the sets are equal-sized (true here) and we interpret the denominator as the maximum possible intersection.

**Choice of $k$.** Reasonable range: $k \in \{5, 10, 20\}$. Report at multiple $k$ to characterise local versus mid-range neighbourhood preservation. Avoid $k > |V|/2$ where the metric becomes uninformative.

**Complexity.** $O(|V|(|V|+|E|))$ for APSP plus $O(|V|^2 \log k)$ for neighbour sorting.

**Source.** Goodhill, Finch and Sejnowski 1996 [Quantifying neighbourhood preservation in topographic mappings](https://consensus.app/papers/details/6abbb2ab8685524c842a715e48a0f5da/?utm_source=claude_desktop) is the formal MDS reference. Used as a graph-drawing metric in [Ahmed et al. 2021 (SGD)²](https://consensus.app/papers/details/81546f0f50d251bfb4429a443ca559eb/?utm_source=claude_desktop). For projection-quality variants see [Martins et al. 2015](https://consensus.app/papers/details/ee1d2db9b17552bf88c8a05ef9ae0c56/?utm_source=claude_desktop).

**Why relevant.** Your compound merging is a deliberate violation of neighborhood preservation in the underlying graph: it pulls equivalent vulnerabilities together visually even when their graph distance differs. Measuring NP$_k$ before and after merging tells the analyst exactly how much "spatial truth" they trade for compactness. This is a strong story.

---

### M12. Trustworthiness and Continuity

A pair of metrics from MDS literature that decompose neighborhood preservation into "false friends" and "missing friends" errors.

**Formulas.** Let $N_k^L(v)$ be layout-$k$-neighbours of $v$, $r_G(v, u)$ the rank of $u$ in $v$'s graph-distance-sorted list. Trustworthiness penalises layout-neighbours that are far in the graph; continuity penalises graph-neighbours that are far in the layout:

$$\mathrm{Trust}_k = 1 - \frac{2}{|V|k(2|V|-3k-1)} \sum_{v} \sum_{u \in N_k^L(v) \setminus N_k^G(v)} (r_G(v,u) - k)$$

$$\mathrm{Cont}_k = 1 - \frac{2}{|V|k(2|V|-3k-1)} \sum_{v} \sum_{u \in N_k^G(v) \setminus N_k^L(v)} (r_L(v,u) - k)$$

**Algorithm.** Same APSP+layout-distance computation as NP$_k$, but track ranks and compute the asymmetric sums.

**Complexity.** $O(|V|^2 \log |V|)$ dominated by sorting.

**Source.** Venna and Kaski 2001, "Neighborhood preservation in nonlinear projection methods: An experimental study". Standard in the t-SNE / UMAP literature.

**Why relevant.** Trustworthiness specifically diagnoses your compound merging: when you put two non-adjacent vulnerabilities into the same parent box, layout-distance becomes near-zero but graph-distance is non-zero, hurting trustworthiness. This is the precise quantification of "did I over-merge?"

---

### M13. Shape-Based Metrics (Proximity Graph Faithfulness)

Compare the proximity graph of the drawing (edges between close points) to the actual graph.

**Formula.** Let $S(D)$ be the proximity graph of the drawing $D$ (e.g., its Gabriel graph or relative neighbourhood graph). The shape-based metric measures how close $S(D)$ is to $G$ via Jaccard similarity of edge sets:

$$\mathrm{SHAPE}(D, G) = \frac{|E(S(D)) \cap E(G)|}{|E(S(D)) \cup E(G)|}$$

**Algorithm.**
1. Compute the Gabriel graph (or RNG) from `pos[]`. Naive: for each pair $(u, v)$, check whether the disk with diameter $\overline{uv}$ contains any other node; cost $O(|V|^3)$. Faster: build the Delaunay triangulation in $O(|V| \log |V|)$ and filter Delaunay edges to retain only those satisfying the Gabriel/RNG condition, total $O(|V| \log |V|)$.
2. Compute the symmetric-difference and intersection of edge sets between $S(D)$ and $G$.
3. Apply the Jaccard formula above.

**Complexity.** $O(|V|^3)$ naive, $O(|V| \log |V|)$ via Delaunay (use `scipy.spatial.Delaunay` in Python).

**Source.** [Meidiana, Hong, Eades and Klein 2022 "Shape-Faithful Graph Drawings"](https://consensus.app/papers/details/85ee4b9e893d50658bab5703a8f330e2/?utm_source=claude_desktop). The dNNG variant in [Nguyen et al. 2017](https://consensus.app/papers/details/5824a845019455d8bd77119f87525f4d/?utm_source=claude_desktop) is more sensitive to subtle differences.

**Why relevant.** Shape-based metrics are designed to work even with non-proximity-preserving drawings, which is exactly the case after your layer-hiding step. Whether your reductions leave a layout that "looks like" the graph in a shape-faithful sense is a defensible question.

---

## Family 3: Information-Preservation Metrics (Specific to Your Reduction)

These match the soundness invariants in your propositions and let you empirically confirm the proofs.

### M14. Reachability Preservation Rate

Empirically validates Proposition 5.1 (bridge-edge soundness).

**Formula.** Sample $K$ pairs $(u, v)$ uniformly from $V' \times V'$ where $V' \subseteq V$ is the set of nodes visible after reduction (excluding any nodes hidden by toggles or contracted into bridge edges). For compound parents, sample at the parent level rather than the child level since this matches what the analyst sees on screen, and define $p_j \rightsquigarrow_{G'} v$ iff $\exists v' \in G_j: v' \rightsquigarrow_G v$ (the parent reaches what any child reaches in $G$).

For each pair, compute reachability in both $G$ and the reduced $G'$:

$$\mathrm{RP}(G, G') = \frac{|\{(u,v) : (u \rightsquigarrow_G v) \Leftrightarrow (u \rightsquigarrow_{G'} v)\}|}{K}$$

**Algorithm.**
1. Sample $K$ pairs $(u, v)$ from $V' \times V'$.
2. For each, BFS from $u$ in $G$ (when $u$ is a compound parent, expand to BFS from each child) and BFS from $u$ in $G'$ (treating bridge edges as single hops).
3. Check whether $v$ is reached in each; when $v$ is a compound parent, $v$ is reached if any of its children is reached in $G$.
4. Record agreement and average.

**Complexity.** $O(K \cdot (|V| + |E|))$.

**Source.** This is your own metric. The inspiration is reachability-querying validation in graph databases; the formal soundness is the bridge-edge soundness proposition in your own paper (Mechanism 2 section).

**Why relevant.** A 100% rate (which your proof predicts) is a one-table addition that closes the gap between proof and implementation. Reviewers love empirically-validated theory. If you find rate < 100%, it's a bug in the implementation.

**Reporting.** Expected to be exactly $1.0$ on every (image, step) cell. State this explicitly and table any deviations rather than aggregating with mean ± std.

---

### M15. Path-Length Preservation

Stronger than reachability. Measures whether the shortest-path distance is preserved (modulo bridge contractions).

**Formula.** Assign each edge $e \in E(G')$ a *weight* $w(e)$ equal to the number of $G$-edges it represents: $w(e) = 1$ for retained edges, $w(e) = $ contracted-chain length for bridge edges (recorded in the bridge-edge provenance map from the Implementation Notes section). Let $d^{G'}_{u,v}$ be the shortest path in $G'$ under these weights. Then:

$$\mathrm{PLP}(G, G') = \frac{1}{K}\sum_{i=1}^{K} \mathbb{1}\!\left[d^G_{u_i,v_i} = d^{G'}_{u_i,v_i}\right]$$

**Algorithm.** Same sampling as RP. Compute $d^G$ via unweighted BFS in $G$ and $d^{G'}$ via Dijkstra in the weighted $G'$. Compare and average. For unreachable pairs, both distances are $\infty$ and count as preserved.

**Complexity.** $O(K \cdot (|V| + |E| \log |V|))$ dominated by Dijkstra.

**Expected value.** PLP should be close to 100% by construction: each bridge edge has weight equal to the contracted chain length, so the weighted shortest path in $G'$ equals the unweighted shortest path in $G$. A measured value below 100% indicates either an implementation bug or a corner case in the bridge construction (for example, multiple parallel chains contracted to one bridge whose weight conflates them).

**Why relevant.** Distinguishes reductions that preserve "is reachable" from those that preserve "how far". The latter is stronger and matters for analyst questions like "what's the shortest path to the most damaging vulnerability."

**Choice of $K$.** Use $K = \min(1000, |V'|^2)$ for typical reporting. For graphs where $|V'| < 32$ (so $|V'|^2 < 1000$), exhaustive enumeration is cheaper than sampling.

**Reporting.** Same convention as M14: expected to be exactly $1.0$ on every cell. Table deviations rather than aggregating.

---

### M16. Typed Out-Signature Preservation Rate

Empirically validates the typed-signature-preservation proposition for compound merging in the paper (Mechanism 3 section).

**Formula.** Define the typed out-signature of a node $v$ in a graph as the multiset $\mathrm{outsig}(v) = \{\!\{ ([w], t) : (v, w) \in E, \tau_E(v,w) = t \}\!\}$, where $[w]$ denotes the ordinal-attribute equivalence class of $w$ (the same equivalence used by the merge key function $k$). For each compound parent $p_j$ and each member $v \in G_j$:

$$\mathrm{TOSP}(G, G') = \frac{|\{(p_j, v) : v \in G_j, \mathrm{outsig}_{G'}(p_j) = \mathrm{outsig}_G(v)\}|}{\sum_j |G_j|}$$

**Algorithm.** For each compound parent $p_j$, compute the multiset of $(\mathrm{class}(\text{target}), \text{type})$ pairs from the consolidated outgoing edges; for each member $v \in G_j$, compute the same multiset from $v$'s pre-merge outgoing edges in $G$; compare for equality.

**Complexity.** $O(|V_i| \cdot \Delta)$ where $\Delta$ is the maximum out-degree.

**Why relevant.** Same value as M14: validates the proof empirically. 100% expected.

**Reporting.** Same as M14 / M15: expected to be exactly $1.0$ on every cell. Table deviations.

---

### M17. Type Coverage

Tracks whether all node types remain represented after reduction.

**Formula.** Let $\mathcal{T}$ be the set of node types in the *original* graph $G$ (before any reduction). Then:

$$\mathrm{TC}(G') = \frac{|\{T \in \mathcal{T} : \exists v \in V', \tau(v) = T\}|}{|\mathcal{T}|}$$

**Algorithm.** Trivial: for each $T \in \mathcal{T}$, scan $V'$ once.

**Why relevant.** When the analyst hides a layer (e.g., "weakness"), TC drops below 1. Reporting TC at each step of the progression makes the abstraction trade-off explicit. Using the original $\mathcal{T}$ as denominator (rather than $\mathcal{T}'$, the types still present after reduction) is what makes this metric meaningful: otherwise hiding a type would trivially keep $\mathrm{TC}(G') = 1$.

---

### M18. Query Equivalence Rate

Generalises reachability preservation to a broader query class.

**Formula.** Define a set $Q$ of analyst queries (e.g., "list all vulnerabilities reachable from external attacker", "list all hosts where attacker can gain root"). For each $q \in Q$:

$$\mathrm{QER}(G, G', Q) = \frac{|\{q \in Q : q(G) = q(G') \text{ up to compound expansion}\}|}{|Q|}$$

**Algorithm.** Hand-define a query corpus; evaluate each on both $G$ and $G'$; compare.

**Complexity.** Depends on query complexity; for reachability queries it is $O(|Q| \cdot (|V|+|E|))$.

**Why relevant.** The most defensible empirical validation that the reductions preserve analyst-relevant information. A query corpus you define yourself becomes a contribution: future work in attack-graph readability has a benchmark.

---

## Family 4: Mechanism-Specific Metrics (Your Contributions)

These are metrics that exist because your three mechanisms exist. They are not in the GD literature; you would essentially own them.

### M19. Bridge-Edge Proportion and Contraction Depth

Characterises how much of the visible graph is synthetic versus retained.

**Formula.**
- Bridge-edge proportion: $\mathrm{BEP}(G') = |E_{\mathrm{bridge}}| / |E(G')|$
- Mean contraction depth: $\mathrm{MCD}(G') = \frac{1}{|E_{\mathrm{bridge}}|}\sum_{e \in E_{\mathrm{bridge}}} (\text{length of contracted chain in } G)$

**Algorithm.** Track bridge-edge provenance during the contraction (the bridge-edge algorithm in Mechanism 2 already produces the chain as part of the construction).

**Complexity.** $O(|E_{\mathrm{bridge}}|)$ once contraction is computed.

**Why relevant.** A reader needs to know whether a typical bridge represents one collapsed node or a chain of five. High MCD with high BEP means the visible graph is heavily synthetic and the bridge-edge colour cue is doing serious work.

**Reporting.** Highly noisy across images — depends on the input scan's chain depth and the user's hide selection. Report mean ± std for both BEP and MCD per step; consider also reporting min and max as the spread is wide.

---

### M20. Edge Consolidation Ratio (Per Compound Parent)

Quantifies the merge mechanism's compression.

**Formula.** For each compound parent $p_j$, restrict attention to edges crossing the parent boundary (exclude edges between two members of the same group, which become intra-parent and are not consolidated). Let:
- $E^{\mathrm{in,raw}}_j = \{(u, v) \in E : v \in G_j, u \notin G_j\}$ (pre-merge incoming)
- $E^{\mathrm{out,raw}}_j = \{(v, w) \in E : v \in G_j, w \notin G_j\}$ (pre-merge outgoing)
- $E^{\mathrm{in}}_j, E^{\mathrm{out}}_j$ = the deduplicated post-consolidation edges from the compound-merging algorithm in Mechanism 3

Then:

$$\mathrm{ECR}(p_j) = \frac{|E^{\mathrm{in,raw}}_j| + |E^{\mathrm{out,raw}}_j|}{|E^{\mathrm{in}}_j| + |E^{\mathrm{out}}_j|}$$

ECR $\ge 1$ always; ECR $= 1$ means no consolidation (each member contributed a distinct edge); ECR $= |G_j|$ means all members had identical incident edges.

**Algorithm.** Track per-group raw and consolidated edge counts during the compound-merging algorithm (the consolidated edges are produced in the deduplication step).

**Complexity.** $O(|E|)$ accumulated across all parents.

**Why relevant.** Reports a per-group compression factor. Histogram of ECR values across compound parents in a single image reveals whether the gain is concentrated in a few large groups or distributed.

**Reporting.** ECR is a per-parent value, so for each (image, step) cell you get a *distribution*, not a scalar. Recommendation: per cell, report the **mean ECR weighted by group size** (so a 50-member group with ECR = 30 dominates a 2-member group with ECR = 2). Then aggregate that weighted mean across images per step using ordinary mean ± std. Skipping the size-weighting hides where the consolidation actually pays off.

---

### M21. Group Cardinality Distribution

Companion to ECR. Reports the size of compound parents.

**Formula.** Histogram of $\{|G_j| : j = 1, \dots, m\}$. Summary statistics to report: count of singletons ($|G_j| = 1$), mean group size, std, max, and (when comparing across images) Gini coefficient of the size distribution.

**Why relevant.** A single histogram per image reveals whether your merge produces many small groups (low cohesion) or few large groups (high cohesion). Combined with ECR, this characterises the merge mode.

**Reporting.** A distribution per cell. Aggregate by reporting the **largest group size** and the **fraction of singletons** as scalar summaries — these are the two numbers an analyst actually wants. Mean ± std across images per step for each.

---

### M22. Attribute Compression Ratio

The upper bound on what merging can achieve.

**Formula.** For each target type $T_i$:

$$\mathrm{ACR}(T_i, G) = \frac{|\{k(v) : v \in V_i\}|}{|V_i|}$$

ACR ranges over $[1/|V_i|, 1]$. ACR $= 1$ means every node has a unique attribute tuple (merge will not compress at all). ACR $= 1/|V_i|$ means all nodes share a single tuple (merge will collapse $V_i$ to one compound parent). The expected reduction factor for the merge step is approximately $1 - \mathrm{ACR}$.

**Algorithm.** Apply key function $k$ to all $V_i$ nodes; count distinct values.

**Complexity.** $O(|V_i|)$ with hashing.

**Why relevant.** Reports the structural compressibility of the input. Across your seven Docker images, this should correlate with how much the merge step contributes to total reduction.

**Reporting.** Per-image scalar (one ACR per type per image). Don't aggregate across images — instead present as a small table (image × type) and visually correlate with achieved reduction. The point of this metric is the cross-image *spread*, not its central tendency.

---

### M23. Slider-Position-vs-Reduction Curve (Type-Zoom Efficiency)

Each per-type slider's effect, plotted as a curve.

**Formula.** For each type $T_i$ and each pivot choice $P_i$ on the slider, record $(N(P_i), E(P_i), C/E(P_i))$ at that slider position. Plot $C/E$ vs slider position per type.

**Algorithm.** Run the slider mechanism at each pivot position; record metrics.

**Why relevant.** Tells the analyst (and reviewer) which slider gives the most readability improvement per granularity step. This is a unique-to-your-paper analysis since nobody else has per-type sliders.

**Reporting.** This is a *curve* per (image, type) — per-image spread is the whole point. Plot all images as faint lines with a bold mean line per type per pivot position (and ± std as a shaded band); do not collapse to a single number per cell.

---

## Family 5: Type-Aware Metrics (Heterogeneous DAG Specific)

Standard graph-drawing metrics ignore node types. Your paper makes the heterogeneous structure central, so your evaluation should follow suit.

### M24. Column Purity

Fraction of nodes placed in the column corresponding to their type. Sugiyama-family layouts should achieve $\sim 1$; the interesting case is cross-layer back-edges (your `ENABLES`).

**Formula.** Let $c(v)$ be the column index assigned to $v$ by the layout, $c^*(\tau(v))$ the column assigned to type $\tau(v)$. Then:

$$\mathrm{CP}(G) = \frac{|\{v \in V : c(v) = c^*(\tau(v))\}|}{|V|}$$

**Algorithm.** Trivial given dagre's column assignments.

**Why relevant.** Confirms your typed schema renders faithfully. The interesting question: does any reduction step degrade column purity (e.g., compound parents that contain different types)?

---

### M25. Type-Pair Crossing Decomposition

Which pairs of edge types contribute most to $C/E$.

**Formula.** For each pair of edge types $(t_1, t_2)$, count crossings between an edge of type $t_1$ and an edge of type $t_2$:

$$X_{t_1, t_2} = |\{(e_1, e_2) \in X : \tau_E(e_1) = t_1, \tau_E(e_2) = t_2\}|$$

Report the matrix or top-$k$ contributing pairs.

**Algorithm.** During crossing detection (Bentley-Ottmann), tag each crossing by the edge types involved.

**Complexity.** $O((|E|+|X|)\log |E|)$ same as basic crossing detection.

**Why relevant.** Pure-novelty metric exploiting your typed schema. In your nginx graph at Step 1 with $C/E = 925$, identifying that, say, 90% of crossings come from `weakness→impact` × `impact→state` would tell you exactly which layers to hide first. You could even auto-recommend the next reduction step based on this.

---

### M26. Edge-Type Distribution

Which edge types contribute most to the visual density.

**Formula.** For each edge type $t \in \mathcal{T}_E$ (where $\mathcal{T}_E$ is the set of edge-type labels in your schema, see Table 1 in your paper):

$$\mathrm{ETD}(t) = \frac{|\{e \in E : \tau_E(e) = t\}|}{|E|}, \quad \mathrm{ETL}(t) = \frac{\sum_{e : \tau_E(e) = t} \|e\|}{\sum_{e \in E} \|e\|}$$

ETD reports the share of each type by count; ETL by total ink (length).

**Algorithm.** Group edges by type; compute counts and length-weighted shares.

**Complexity.** $O(|E|)$.

**Why relevant.** Your `ENABLES` back-edges span across the layered direction and contribute disproportionately to crossings and total ink. Reporting ETD and ETL isolates their visual cost. Note that in a strictly layered DAG with one type per layer, intra-type edges (between two nodes of the same type) cannot exist by definition; in your schema only `ENABLES` violates strict layering, and only between state and vulnerability nodes (different types). So strictly speaking we report a per-type-pair distribution, not "inter vs intra." The original section title was misleading; the metric is just the edge-type mix.

---

### M27. Layer Balance

Coefficient of variation of node counts across the layout's layers. In your schema each type maps to one layer ($\lambda(T_i)$ is bijective up to back-edges), so layers and types coincide and this metric is equivalent to "type-population balance."

**Formula.** Let $n_\ell$ be the number of nodes in layer $\ell$, where $\ell$ ranges over the $L$ layers in the layout. In PAGDrawer's schema $L = 7$ (ATTACKER, HOST, CPE, CVE, CWE, TI, VC), or $L = 8$ if the BRIDGE pseudo-layer is included (`getColumnPositions()` assigns it rank 7). Pick one convention and apply it across all reported numbers; the recommendation is $L = 7$ — exclude the bridge from balance because there is at most one BRIDGE node and including it skews $\sigma$ downwards. Then:

$$\mathrm{LB}(G) = \frac{\sigma(n_1, \dots, n_L)}{\mu(n_1, \dots, n_L)}$$

Lower is better-balanced; 0 means all layers have the same count.

**Algorithm.** Bucket nodes by layer (read off the dagre layer assignment, or compute as `lambda(type[v])`); compute mean and stdev.

**Complexity.** $O(|V|)$.

**Why relevant.** A heavily-imbalanced layered drawing has wasted vertical space (some layers crowded, others sparse). After your reductions, balance should improve as the dominant layers (typically vulnerability, weakness, impact in attack graphs) shrink toward the smaller layers (host, attacker).

---

## Family 6: Visual-Density and Clutter Metrics

Bridge between objective measurements and perceived complexity. Useful for setting up the user-study story.

### M28. Visual Clutter Score

Quantifies "how busy" the drawing looks.

**Formula sketch.** Bertini and Santucci 2004 define clutter as the inverse of the perceptible-pattern density. A simple proxy for graphs: clutter increases with $|E|$, with edge crossings, with edge length variance, and with node overlap; it decreases with bounding-box area.

The reportable formula uses each component normalised to $[0, 1]$ across the image corpus, then averaged with equal weights:

$$\mathrm{CLUT}(G) = \frac{1}{3}\Big[\, \widetilde{ED}(G) + \widetilde{C/E}(G) + \widetilde{\mathrm{CV}_\ell}(G) \,\Big]$$

where $\widetilde{X}(G) = (X(G) - \min_{G' \in \mathcal{C}} X(G')) / (\max_{G' \in \mathcal{C}} X(G') - \min_{G' \in \mathcal{C}} X(G'))$ is the min-max normalisation across the image corpus $\mathcal{C}$, and the three components are edge density $|E|/A_{\mathrm{bbox}}$, crossings-per-edge $|X|/|E|$, and edge-length CV $\sigma_\ell/\mu_\ell$.

[^clut-raw]: The unnormalised composite $\alpha \cdot |E|/A_{\mathrm{bbox}} + \beta \cdot |X|/|E| + \gamma \cdot \sigma_\ell/\mu_\ell$ with arbitrary weights is dimensionally inconsistent (the first term has units of inverse area, the others are dimensionless). The weights would have to absorb this difference. The min-max normalisation makes all three terms dimensionless before weighting and removes the calibration burden.

**Source.** Bertini and Santucci 2004 "Quality metrics for 2D scatterplot graphics: Automatically reducing visual clutter" (general visualisation) and Rosenholtz et al. 2007 "Measuring visual clutter" (vision science). Adapted for graphs in various GD papers.

**Why relevant.** A single-number summary that aggregates several of the above. Useful for executive-summary tables. Be honest about the calibration: report the components separately too.

---

### M29. Information Density

Bits of distinguishable information per unit area. Relevant for "fits on a screen" claims.

**Formula sketch.** Approximate as $\log_2(N \cdot E) / A_{\mathrm{bbox}}$, where the numerator estimates the information content and the denominator is the area.

**Why relevant.** The end-state of your reductions should have higher information density per unit area: each visible element conveys more meaning. Worth quantifying.

---

### M30. Total Ink Reduction Ratio

Tufte-inspired. Reports how much rendered "ink" (edges plus node markings) the reduction removed.

**Formula.** Two variants depending on rendering convention:
- For *outlined* nodes (stroke only): $\mathrm{INK}(G) = \sum_e \|e\| \cdot w_e + \sum_v 2\pi r_v \cdot w_v$ where $w_e, w_v$ are edge stroke width and node stroke width respectively.
- For *filled* nodes (default in Cytoscape.js with dagre): $\mathrm{INK}(G) = \sum_e \|e\| \cdot w_e + \sum_v \pi r_v^2$ where $\pi r_v^2$ is the filled disk area.

Use whichever matches your renderer. Reduction ratio: $\mathrm{INK}(G_1) / \mathrm{INK}(G_{5.2}) \ge 1$, indicating "ink removed factor."

**Why relevant.** Direct visual quantification of how much "marking" you removed. Easy to compute, easy to explain to non-graph-drawing audiences.

---

## Cognitive and Task Metrics (For the Future User Study)

These belong in the future-work limitation paragraph, not the current evaluation. Listed for completeness because your user-study limitation is the single biggest acceptance risk and you should signal that you know exactly what you would measure.

- **Task accuracy** on path-tracing, vulnerability prioritisation, cross-host comparison
- **Task completion time** with controlled task difficulty
- **NASA-TLX cognitive load** rating (six-dimensional questionnaire)
- **Confidence rating** per task (5-point Likert)
- **Eye-tracking** metrics: fixation count, fixation duration on target nodes, scan-path length, areas-of-interest dwell time
- **Pupil dilation** as cognitive-load proxy (used by [Yoghourdjian et al. 2020](https://consensus.app/papers/details/9172c318ab77528d9e45281113765623/?utm_source=claude_desktop))
- **EEG** band power (alpha, theta) for engagement and load (also Yoghourdjian et al. 2020)

---

## How I would prioritise

If you can implement only one new metric, **stress** (M1). It is the most expected metric in modern GD evaluation; reviewers will look for it.

If you can implement three: stress (M1), mean and minimum **crossing angle** (M2), and **reachability preservation rate** (M14). The first two strengthen the layout-quality story; the third closes the proof-versus-implementation gap.

If you can implement five (the ones I'd actually report in the body): the above three plus **edge consolidation ratio** (M20) for the merge mechanism and **type-pair crossing decomposition** (M25) for the heterogeneous schema. The remaining metrics in this document go into an appendix.

For the appendix-only metrics, my recommendations are: **neighborhood preservation** (M11) and **trustworthiness** (M12) for the dimension-reduction-style story, **bridge-edge proportion and contraction depth** (M19) for transparency about how synthetic the reduced graph is, **attribute compression ratio** (M22) to predict per-image reducibility, **column purity** (M24) and **edge-type distribution** (M26) for the heterogeneous schema, and **clutter score** (M28) as an executive summary.

The metrics I would NOT pursue further unless you find a concrete reason: symmetry (M6), continuity (M7), and information density (M29). They are good for general layout evaluation but do not connect tightly to your three mechanisms' claimed benefits.

## Common pitfalls

The first pitfall is **metric soup**: reporting fifteen numbers and letting reviewers find the one that does not move. Pick the metrics that align with your three mechanisms' claimed benefits, report all of them honestly, and discuss the ones that move the wrong way.

The second is **no baseline**. You compare Step 5.2 against Step 1, but both use your dagre layout. A reviewer might ask: how does Step 1 with dagre compare to Step 1 with force-directed (Fruchterman-Reingold)? You don't need to win every comparison, but showing two layouts and that your mechanisms help in both would close the "this only works because dagre is bad" objection.

The third is **size-dependent metrics without normalisation**. You did this right with $C/E$ instead of raw crossings. Apply the same logic to stress (per pair) and edge consolidation (ratio not absolute count).

The fourth is **ignoring perceptual literature**. The crossing-angle and continuity metrics matter because controlled human studies show they affect path-tracing performance. Citing those studies when you justify your metric choice gives reviewers a perceptual rationale beyond "more crossings = bad".

The fifth is **claiming improvement when the metric is dominated by graph size**. Your $A/N$ counterexample (postgres and redis) is a credibility-builder when you discuss it honestly. Doing the same for any metric that moves the wrong way protects against the appearance of cherry-picking.

The sixth is **not running an ablation**. The Di Bartolomeo et al. 2024 review explicitly criticises the "Wild West" of benchmark datasets in GD evaluation. Generating synthetic layered heterogeneous DAGs with controlled parameters (number of types, layers, attribute cardinality) lets you isolate which mechanism contributes which fraction of the reduction. A one-paragraph appendix on this would be reviewer-proof methodological grounding.

## Sources

The full set of papers cited above:

- [Purchase 1997 "Which Aesthetic has the Greatest Effect on Human Understanding?"](https://consensus.app/papers/details/7bff0d94671c5958b6117cc76388c7e1/?utm_source=claude_desktop)
- [Purchase 2002 "Metrics for Graph Drawing Aesthetics"](https://consensus.app/papers/details/dfb363e909f9532a91fa2172dd65a7e2/?utm_source=claude_desktop)
- [Purchase et al. 2002 "Empirical Evaluation of Aesthetics-based Graph Layout"](https://consensus.app/papers/details/66a2faadc4bf5ceda5d62beca0029c6e/?utm_source=claude_desktop)
- [Ware, Purchase, Colpoys and McGill 2002 "Cognitive Measurements of Graph Aesthetics"](https://consensus.app/papers/details/f90732290c375b9589d8c00b78fda373/?utm_source=claude_desktop)
- [Gansner, Koren and North 2004 "Graph Drawing by Stress Majorization"](https://consensus.app/papers/details/b2f5a4dbd7fc5e0e81da68bc75b3268b/?utm_source=claude_desktop)
- [Huang 2007 "Using eye tracking to investigate graph layout effects"](https://consensus.app/papers/details/a33b29c030795891ace981ab9652e73b/?utm_source=claude_desktop)
- [Argyriou et al. 2010 "Maximizing the Total Resolution of Graphs"](https://consensus.app/papers/details/71be2d8b6cff599cb8db32006d96ed30/?utm_source=claude_desktop)
- [Khoury et al. 2012 "Drawing Large Graphs by Low-Rank Stress Majorization"](https://consensus.app/papers/details/8fe2e76425d859a8b81e184e8c745a89/?utm_source=claude_desktop)
- [Didimo, Eades and Liotta 2013 "The Crossing-Angle Resolution in Graph Drawing"](https://consensus.app/papers/details/969658f9042d5ceaa7aab24e74680e02/?utm_source=claude_desktop)
- [Huang, Eades and Hong 2014 "Larger crossing angles make graphs easier to read"](https://consensus.app/papers/details/f83e52e93715565eab6519f0062f7d32/?utm_source=claude_desktop)
- [Martins et al. 2015 "Explaining Neighborhood Preservation for Multidimensional Projections"](https://consensus.app/papers/details/ee1d2db9b17552bf88c8a05ef9ae0c56/?utm_source=claude_desktop)
- [Welch and Kobourov 2017 "Measuring Symmetry in Drawings of Graphs"](https://consensus.app/papers/details/730e7f78b2e75ac5b4eada4c0b4477e7/?utm_source=claude_desktop)
- [Nguyen et al. 2017 "dNNG: Quality metrics and layout for neighbourhood faithfulness"](https://consensus.app/papers/details/5824a845019455d8bd77119f87525f4d/?utm_source=claude_desktop)
- [Devkota et al. 2019 "Stress-Plus-X (SPX) Graph Layout"](https://consensus.app/papers/details/cc2585e471c55856a95c93e31ea58501/?utm_source=claude_desktop)
- [Yoghourdjian et al. 2020 "Scalability of Network Visualisation from a Cognitive Load Perspective"](https://consensus.app/papers/details/9172c318ab77528d9e45281113765623/?utm_source=claude_desktop)
- [Meidiana et al. 2020 "Quality Metrics for Symmetric Graph Drawings"](https://consensus.app/papers/details/ddd76edf521e50bc808554dd4048a2ec/?utm_source=claude_desktop)
- [Ahmed et al. 2021 "Multicriteria Scalable Graph Drawing via SGD²"](https://consensus.app/papers/details/81546f0f50d251bfb4429a443ca559eb/?utm_source=claude_desktop)
- [Meidiana et al. 2022 "Shape-Faithful Graph Drawings"](https://consensus.app/papers/details/85ee4b9e893d50658bab5703a8f330e2/?utm_source=claude_desktop)
- [Meidiana et al. 2022 "Automorphism Faithfulness Metrics for Symmetric Graph Drawings"](https://consensus.app/papers/details/027d408e736f5e0684e66fcf47e86d14/?utm_source=claude_desktop)
- [Mooney et al. 2024 "The Multi-Dimensional Landscape of Graph Drawing Metrics"](https://consensus.app/papers/details/0d8758af083a5ada8c614a5f32cfc2e7/?utm_source=claude_desktop)
- [Mooney et al. 2024 "The Perception of Stress in Graph Drawings"](https://consensus.app/papers/details/2b6c0dc1e39256248d1e5d4ce0949e2e/?utm_source=claude_desktop)
- [Di Bartolomeo et al. 2024 "Evaluating Graph Layout Algorithms: A Systematic Review"](https://consensus.app/papers/details/f6c9328902fd58de88782e4eff303d7a/?utm_source=claude_desktop)
- [Goodhill, Finch and Sejnowski 1996 "Quantifying neighbourhood preservation in topographic mappings"](https://consensus.app/papers/details/6abbb2ab8685524c842a715e48a0f5da/?utm_source=claude_desktop)
- [Bauer and Pawelzik 1992 "Quantifying the neighborhood preservation of self-organizing feature maps"](https://consensus.app/papers/details/f826d6175ea35a55934329ca30c8d42b/?utm_source=claude_desktop) — early formal treatment of neighbourhood preservation, predates the MDS-graph-drawing connection but worth knowing for M11.
- Venna and Kaski 2001, "Neighborhood preservation in nonlinear projection methods: An experimental study," ICANN 2001 — original paper for the trustworthiness/continuity formula in M12.
