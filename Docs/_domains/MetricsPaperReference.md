# Metrics — Paper Reference

A single reference document for the GD 2026 paper. Covers exactly what's implemented in PAGDrawer, how each metric is expected to move when the user applies one of the reduction mechanisms, the concessions made along the way, paper-ready algorithms for the methodology section, and the recommended evaluation procedure.

For deeper per-area material:
- [`DrawingQualityMetrics.md`](DrawingQualityMetrics.md) — per-metric API summary and CSV column ordering
- [`StressMetric.md`](StressMetric.md) — the directed-graph stress adaptation in full
- [`StatisticsModal.md`](StatisticsModal.md) — UI surface and full JSON schema
- [`../Plans/metric_proposals.md`](../Plans/metric_proposals.md) — the wider catalogue this implementation drew from

---

## 1. Implemented metrics

Twelve metrics across two papers' worth of GD literature, plus three normalised stress variants. Body-of-paper set is **M1, M2, M20, M25**; appendix-friendly extras are **M9, M19, M21**. Stages 5–7 of the metrics roadmap will add M3, M11, M12, M22, M24, M26.

| ID  | Name                                | Family                | Type                  | Status |
|-----|-------------------------------------|-----------------------|-----------------------|--------|
| M1  | Stress (per-pair, symmetrised)      | Layout aesthetic      | scalar + 3 normalised | ✓      |
| M2  | Crossing-angle metrics              | Layout aesthetic      | mean / min / RAC      | ✓      |
| M9  | Aspect ratio                        | Layout aesthetic      | scalar                | ✓      |
| M19 | Bridge edge proportion + depth      | Mechanism-specific    | 2 scalars + dict      | ✓      |
| M20 | Edge consolidation ratio (weighted) | Mechanism-specific    | scalar                | ✓      |
| M21 | Compound group cardinality          | Mechanism-specific    | 3 scalars + dict      | ✓      |
| M25 | Type-pair crossing decomposition    | Type-aware            | scalar + label + dict | ✓      |

Plus the existing baseline: **node count**, **edge count**, **edge crossings (raw)**, **crossings normalised** (Purchase 2002), **crossings per edge**, **drawing area**, **bbox width**, **bbox height**, **area per node**, **edge length CV**, **unique CVE count**, **Trivy vulnerability total**.

JSON export at schema v1 also carries: per-edge-type-pair distribution dict (M25), per-bridge chain-length distribution dict (M19), per-compound size distribution dict (M21), per-compound ECR breakdown array (M20), full settings snapshot, build provenance (`git_sha`, `app_version`), and data-source metadata.

---

## 2. Per-metric specification

### M1 — Stress (Purchase 2002, Kamada-Kawai-style)

**Definition.** For every reachable unordered pair `(i, j)`:

$$
S(G) = \frac{1}{|\mathcal{R}|} \sum_{(i,j) \in \mathcal{R}} \left( \frac{\| p_i - p_j \|_2}{\sigma} - d_{ij} \right)^{\!2}
$$

where $p_i \in \mathbb{R}^2$ is node $i$'s layout position, $d_{ij}$ is the symmetrised graph distance, $\mathcal{R}$ is the set of reachable pairs, and $\sigma$ is one of four scale factors:

| Variant                                 | $\sigma$                  | Convention                  |
|-----------------------------------------|---------------------------|-----------------------------|
| `stress_per_pair`                       | $1$                       | raw (units mixed)           |
| `stress_per_pair_normalized_edge`       | $\bar{\ell}$ (mean edge)  | Kamada-Kawai 1989           |
| `stress_per_pair_normalized_diagonal`   | $\sqrt{w^2 + h^2}$        | Mooney 2024                 |
| `stress_per_pair_normalized_area`       | $\sqrt{w \cdot h}$        | Drawing-area variant        |

**Symmetrised distance.** Because PAGDrawer's graph is directed (DAG with `ENABLES` back-edges) and Euclidean is symmetric, the graph-side distance is symmetrised:

$$
d_{ij} = \min\!\bigl(d_{i \to j},\; d_{j \to i}\bigr) \in \mathbb{N} \cup \{\infty\}
$$

If $d_{ij} = \infty$ the pair is unreachable and dropped from the mean (skip-and-report convention; the count is reported as `stress_unreachable_pairs`).

**What it measures.** Layout faithfulness — how well visible distance reflects topological distance. Lower is better; 0 is impossible for any non-tree graph.

**Algorithm complexity.** Directed BFS from every node: $O(|V| \cdot (|V| + |E|))$. Per-pair iteration: $O(|V|^2)$ once over the upper triangle. Total stays well below 1 second for graphs up to ~500 nodes.

**Visualisations** (interactive, click-driven):
- Click a node → every reachable node recolours red→yellow→green by symmetrised distance (HSL hue $\propto d_{ij}/d_{\max}$); unreachable greys out.
- Click two nodes in sequence → floating panel shows $d_{i \to j}$, $d_{j \to i}$, $d_{ij}$, $\| p_i - p_j \|$.

Full discussion in [`StressMetric.md`](StressMetric.md).

### M2 — Crossing-angle metrics (Huang, Eades, Hong 2014)

For each pair of crossing edges $(e_1, e_2)$, compute the acute angle:

$$
\theta(e_1, e_2) = \mathrm{arctan2}\!\bigl(|\vec{e_1} \times \vec{e_2}|,\; |\vec{e_1} \cdot \vec{e_2}|\bigr) \in [0, \pi/2]
$$

The absolute value on both arguments folds the result into the acute range regardless of edge orientation.

Three derived scalars:

- $\bar\theta$ — mean over crossings (`crossings_mean_angle_deg`)
- $\theta_{\min}$ — minimum (`crossings_min_angle_deg`)
- $\rho_{\mathrm{RAC}}$ — fraction of crossings with $|\theta - \pi/2| \le \pi/12$ (i.e. within ±15° of right angle), `crossings_right_angle_ratio`

**What it measures.** Path-tracing readability. Larger angles ease visual disambiguation; mean closer to 90° and high RAC indicate easier-to-read crossings.

**Visualisation.** Crossings are already drawn as red dots (Purchase-style debug overlay). M2 toggles colour them by angle: $\mathrm{HSL}(120^\circ \cdot \theta / (\pi/2),\, 75\%, 50\%)$. Red ≈ acute / bad; green ≈ orthogonal / good.

### M9 — Aspect ratio

$$
\mathrm{AR}(G) = \frac{\min(w, h)}{\max(w, h)} \in [0, 1]
$$

where $(w, h)$ are the bbox dimensions. 1 = square, $\to 0$ = degenerately elongated. Reported as `aspect_ratio`. Bbox is also exposed directly as `bbox_width`, `bbox_height`, `drawing_area`.

**Visualisation.** Toggle appends `(AR = 0.42)` to the bbox label.

### M19 — Bridge edge proportion + contraction depth

PAGDrawer's visibility toggles replace chains of hidden nodes with single bridge edges. Each bridge carries `chain_length` = number of hidden intermediate nodes:

- $\mathrm{BEP}(G) = \frac{|\mathcal{B}|}{|E|}$ — `bridge_edge_proportion`, `mean_contraction_depth = (1/|\mathcal{B}|) \sum_{b \in \mathcal{B}} \mathrm{chainLen}(b)`
- $\mathrm{bridge\_edge\_count} = |\mathcal{B}|$
- Full per-chain-length distribution as a JSON-only dict

**What it measures.** Transparency about how synthetic the reduced graph is. A low contraction depth means bridges represent single-hop hides; high depth means the metric is summarising deeper paths.

**Computation.** `chain_length` accumulates over chained `hideNodeType` calls. When hiding type $T$ at node $n$, with predecessor $p$ and successor $s$:

$$
\mathrm{chainLen}_{\mathrm{new}} = \mathrm{chainLen}(p \!\to\! n) + 1 + \mathrm{chainLen}(n \!\to\! s)
$$

Original (non-bridge) edges count as 0. Algorithm in §4 below.

**Visualisation.** Toggle adds `k=N` labels at the midpoint of each bridge edge.

### M20 — Edge consolidation ratio (per compound parent)

For each compound parent $p$ produced by `merge by outcomes`:

$$
\mathrm{ECR}(p) = \frac{\text{raw edges incident on visible children of } p}{\text{synthetic edges incident on } p}
$$

Aggregated as a **size-weighted mean** (weighted by visible-child count):

$$
\overline{\mathrm{ECR}}_w = \frac{\sum_p \mathrm{ECR}(p) \cdot |\mathrm{children}_{\mathrm{vis}}(p)|}{\sum_p |\mathrm{children}_{\mathrm{vis}}(p)|}
$$

over compounds with $\ge 1$ synthetic edge (excludes ATTACKER_BOX, prereqs-mode merge groups, and any compound the merge mechanism didn't add synthetic edges to).

Reported as `mean_ecr_weighted`, `ecr_compounds_count`. Per-compound breakdown in JSON-only `ecr_per_compound`.

**What it measures.** Per-image consolidation factor. ECR×3.4 means the merge replaced ~3.4 originals with one synthetic edge for each child of the compound, on average across the compound parents.

**Visualisation.** Toggle appends `(ECR×N.M)` to compound parent labels. Composes with M21:

```
M21 alone:   "Outcome XYZ  (×5)"
M20 alone:   "Outcome XYZ  (ECR×3.4)"
both:        "Outcome XYZ  (×5  ECR×3.4)"
CVE_GROUP whose backend label already includes "(×5)":
             "Outcome (×5)  (ECR×3.4)"  (M21 detects pre-existing suffix)
```

### M21 — Compound group cardinality (generalised)

For every compound parent $p$ across all types (CVE_GROUP, COMPOUND/ATTACKER_BOX, future):

- `compound_groups_count` — total number of compound parents with $\ge 1$ visible child
- `compound_largest_group_size` — $\max_p |\mathrm{children}_{\mathrm{vis}}(p)|$
- `compound_singleton_fraction` — fraction of parents with exactly one visible child
- `compound_size_distribution` — JSON-only dict, e.g. `{2: 5, 3: 8, 8: 1}`

**Note on singleton fraction.** Stays at 0 in normal operation: `cveMerge.ts:176` skips groups with `<2` members. Kept as a regression sentinel — if a future merge mode produces singletons, this surfaces immediately.

**Visualisation.** Toggle appends `(×N)` to every compound parent's label. Idempotent — skips parents whose backend label already includes `(×<digits>)` (e.g. CVE_GROUP).

### M25 — Type-pair crossing decomposition

Tag every crossing $(e_1, e_2)$ with the lexicographically-sorted pair of edge types:

$$
X_{t_1, t_2} = |\{(e_1, e_2) \in X \mid \tau(e_1) = t_1, \tau(e_2) = t_2\}|
$$

Reported scalars:
- `crossings_top_pair_share` — top type-pair's share of all crossings
- `crossings_top_pair_label` — its label, e.g. `"HAS_VULN×LEADS_TO"` (RFC 4180-quoted in CSV when needed)
- `crossings_type_pair_distribution` — JSON-only dict (variable cardinality)

Tie-breaking on top: lexicographic on the label key (deterministic, important for CSV stability).

**What it measures.** Pure-novelty exploiting PAGDrawer's typed schema. Identifies which pair of edge types is causing the bulk of visual cost. Useful for selecting *which* layer to hide first.

**Visualisation.** Crossing dots coloured by type pair (10-colour categorical palette ordered by frequency, most-common pair = red).

---

## 3. Expected behaviour under reduction mechanisms

The four mechanisms PAGDrawer offers, mapped to predicted metric movement. ↓ = expected to decrease, ↑ = increase, ≈ = roughly unchanged, ⚠ = caveat.

### Granularity sliders

Tighter granularity (e.g. CVE per HOST → CVE per CWE → CVE singular) collapses duplicated nodes into shared instances.

| Metric                       | Direction | Why |
|------------------------------|-----------|-----|
| $|V|, |E|$                   | ↓         | duplicates removed |
| crossings_raw                | ↓ ↓       | fewer edges, fewer pairs to cross |
| crossings_per_edge           | ≈ to ↓    | depends on layout; usually drops |
| stress_per_pair_*            | ↓         | smaller graph, layout fits topology better |
| M2 mean_angle_deg            | ↑ slowly  | residual crossings tend to be the structural ones (often more orthogonal) |
| M9 aspect_ratio              | ⚠         | unpredictable; depends on which layer compressed most |
| M21 compound_*               | unchanged | granularity doesn't create compounds |
| M19 bridge_*                 | unchanged | no visibility toggle yet |
| M20 ECR                      | unchanged | no merge yet |
| M25 top_pair_label           | may shift | sometimes the dominant pair changes when one type compresses |

### Visibility toggles (hide CWE, hide TI, etc.)

Each hide creates bridge edges replacing the path through the hidden type.

| Metric                       | Direction | Why |
|------------------------------|-----------|-----|
| $|V|$                        | ↓ ↓       | whole layer removed |
| $|E|$                        | ⚠         | originals removed but bridges added; net depends on chain branching |
| crossings_raw                | ↓ ↓ ↓     | typically the largest single-step drop |
| crossings_per_edge           | ↓         | layout simplifies |
| stress_per_pair_*            | ↓         | shorter chains → easier to lay out faithfully |
| M2 mean_angle_deg            | ↑         | survivors are usually structural (orthogonal) |
| M19 bridge_edge_proportion   | 0 → > 0   | by construction |
| M19 mean_contraction_depth   | = 1, then accumulates | hide CWE → 1, hide CWE+TI → 2 (chained bridges) |
| M20 ECR                      | ≈         | no compound parents yet |
| M21 compound_*               | unchanged ⚠ | unless ATTACKER_BOX changes |
| M25 top_pair_label           | shifts ↑↑ | which edge-type pair dominates changes after each layer hide |

### CVE merge by outcomes

Groups CVEs sharing an outcome key into compound parents; original CVE↔outside edges are hidden, synthetic compound↔outside edges are added.

| Metric                       | Direction | Why |
|------------------------------|-----------|-----|
| $|V|$                        | ↑ slightly | new compound parents added (children stay) |
| $|E|$                        | ↓ ↓       | many originals replaced with fewer synthetics |
| crossings_raw                | ↓         | edges deduplicated through synthetic compound edges |
| crossings_per_edge           | ↓         | usually significant |
| stress_per_pair_*            | ⚠         | may rise — children become disconnected from outside; see §4 |
| stress_unreachable_pairs     | ↑ ↑       | by construction; expect $|\mathrm{children}| \cdot (|V| - |\mathrm{children}|)$ |
| M19 bridge_*                 | unchanged | merge doesn't affect bridges |
| M20 ECR                      | 0 → > 1   | the headline number for this mechanism |
| M21 compound_groups_count    | ↑ ↑       | every merge group adds a parent |
| M21 largest_group_size       | tracks merge concentration | |
| M25 top_pair_label           | may shift to synthetic types (`SYN_…`) | |

### Exploit Paths filter

Hides nodes/edges that aren't on a path from initial state to terminal goals.

| Metric                       | Direction | Why |
|------------------------------|-----------|-----|
| $|V|, |E|$ (visible)         | ↓ ↓       | filter is task-driven, often aggressive |
| crossings_raw                | ↓         | proportional to edge drop |
| stress_per_pair_*            | ↓         | smaller surviving graph |
| stress_unreachable_pairs     | ↓         | many unreachable pairs are now invisible |
| M19, M20, M21                | unchanged structurally | counts may drop as hidden compounds excluded (visibility filter applied per metric) |
| M9 aspect_ratio              | ⚠         | layout may not relayout; bbox of survivors only |

### Composing mechanisms

The metrics are largely orthogonal; their movements compose. The recommended order (§5 below) applies them cumulatively so each step's contribution is computable from the table.

---

## 4. Caveats, idiosyncrasies, concessions

Honest engineering notes for the methodology section. Reviewers asking "but what about X" should find their answer here.

### 4.1 Symmetrised stress on a directed graph

PAGDrawer's graph is directed but Euclidean isn't. We chose `min(d_{i→j}, d_{j→i})` over (a) treating the graph as undirected or (b) reporting strict-directed stress. Rationale and trade-offs in [`StressMetric.md`](StressMetric.md) §"What PAGDrawer ships". A pair reachable in only one direction *still contributes* to the metric — the alternative would mark ~50% of pairs unreachable in any layered DAG.

### 4.2 Unweighted graph → BFS, not Dijkstra/Floyd-Warshall

Edges are unweighted. BFS computes single-source shortest paths in $O(|V|+|E|)$, which is optimal. Naming the helper after Dijkstra would suggest weighted-graph machinery the metric does not need. Floyd-Warshall is $O(|V|^3)$, much worse on sparse PAGDrawer graphs.

### 4.3 Stress with compound nodes is noisy on the unreachable counter

Outcomes-merge sets `display: none` on original CVE↔outside edges and adds synthetic compound↔outside edges. The CVE children remain `:visible` but graph-disconnected (their only "connections" are now hidden). Stress includes them as nodes but they can't reach anything via visible edges, so `stress_unreachable_pairs` inflates by `|merged children| · (|V| − |merged children|)`.

The reachable-pair stress is correct; the unreachable count is just noise on the side counter. **Always report `stress_reachable_pairs` alongside.** Cleanest future fix is a "node has at least one visible edge" filter — handles outcomes and prereqs modes uniformly. Documented in [`StressMetric.md`](StressMetric.md) §"Behaviour with compound nodes".

### 4.4 Variable-cardinality dicts are JSON-only

Four metrics produce per-bucket distributions whose key set varies by graph:

- `compound_size_distribution` (M21)
- `bridge_chain_length_distribution` (M19)
- `crossings_type_pair_distribution` (M25)
- `ecr_per_compound` (M20, an array)

These are **JSON-only**. Flat-columning them in CSV would produce unstable headers across runs (different graphs have different keys), breaking diff/concat workflows. CSV instead carries summary scalars: `_largest_group_size`, `_top_pair_label`, etc.

### 4.5 M20 excludes empty-synthetic compounds

M20's denominator is undefined when a compound has no synthetic edges. We exclude such compounds entirely (ATTACKER_BOX, prereqs-mode merge groups, unmerged compounds). The reported `ecr_compounds_count` is the size of the non-empty set; combined with `compound_groups_count` from M21 a reader can see how many compounds the metric was actually computed over.

### 4.6 Layout invariance

All metrics use **logical Cytoscape coordinates** (`cy.position()`), not screen pixels. Zoom and pan don't affect the numbers — same graph zoomed in vs. zoomed out produces identical stress, identical crossings, identical bbox. Verified by every "should be invariant under zoom" assertion in the test suite.

### 4.7 Build-time provenance

JSON exports include `git_sha` (from `git rev-parse HEAD` at Vite build time) and `app_version` (from `frontend/package.json`). Replaces an earlier proposal of a hand-maintained `metric_version` field. **Caveat**: the SHA reflects HEAD even if the working tree has uncommitted changes — anyone publishing a paper figure should run on a clean tree.

### 4.8 Visibility filtering is consistent across metrics

Every metric uses the same predicate for "visible":

```
node is visible
  ⇔ (not :hidden by stylesheet)
  ∧ (not exploit-hidden class)
  ∧ (not display:none)
  ∧ (type ∉ {CROSSING_DEBUG, AREA_DEBUG, UNIT_EDGE_NODE})
```

Compound parents that have `.exploit-hidden` class or `display: none` are excluded from M20 and M21 (and M21 only counts visible children regardless of parent visibility).

### 4.9 Crossing detection is brute-force $O(|E|^2)$

We don't use Bentley-Ottmann ($O((|E|+|X|)\log |E|)$) because:
1. PAGDrawer's typical $|E|$ is 100s, not thousands — brute-force is microseconds.
2. We need every crossing's edge-type pair anyway (M25), which Bentley-Ottmann doesn't give for free.
3. Sweep-line implementation in TypeScript is non-trivial and not worth the maintenance burden for current scales.

If a future scan pushes $|E|$ above ~5,000, this would be the first thing to optimise.

### 4.10 Type-pair sorting

For M25, every crossing's pair is sorted lexicographically before being keyed: `(B_TYPE, A_TYPE)` and `(A_TYPE, B_TYPE)` collapse into one bucket `"A_TYPE×B_TYPE"`. Tie-breaking on the top pair is also lex-first. Both choices keep CSV exports deterministic across repeated runs of the same input.

### 4.11 chain_length accumulation depends on hide order

M19's `chain_length` accumulates correctly only because `hideNodeType` is called sequentially per type. If a future API hides multiple types atomically without going through the per-type bridge-creation logic, chain_length would need to be recomputed. The current implementation is correct for the UI workflow (one type per click).

### 4.12 Stress visualisation: APSP per click

Each click in the stress-distance-coloring overlay recomputes APSP from scratch. No within-modal cache yet. For typical PAGDrawer graphs ($|V| < 200$) this is sub-millisecond. For the largest scans, expect ~50 ms per click. A cache keyed on `(visible-node-set, visible-edge-set)` is on the post-Stage-7 wishlist (M11/M12 will need the same cache).

---

## 5. Algorithms (paper-ready pseudocode)

The following pseudocode matches the actual TypeScript implementations one-to-one. File and function references are given so reviewers can verify against the source.

### 5.1 BFS-based directed APSP

`computeAPSP` in `frontend/js/features/metrics.ts`:

```
function APSP(V, E, directed=true):
    adj := empty map from id → list of ids
    for v in V: adj[v] := []
    for (u, v) in E:
        if u, v ∈ V and u ≠ v:
            adj[u].append(v)
            if not directed: adj[v].append(u)

    D := empty map from id → (map from id → int)
    for s in V:
        D[s] := { s ↦ 0 }
        Q := [s]
        while Q is non-empty:
            u := Q.pop_front()
            for v in adj[u]:
                if v ∉ D[s]:
                    D[s][v] := D[s][u] + 1
                    Q.push_back(v)
    return D
```

**Complexity.** $O(|V| \cdot (|V| + |E|))$. Each BFS is $O(|V|+|E|)$; we run $|V|$ of them.

**Notes for paper.** The graph is unweighted; BFS computes single-source shortest paths exactly. Self-loops are ignored (they don't affect shortest paths). Edges with endpoints not in $V$ are skipped defensively (handles cases where the visible-set filter excluded one endpoint).

### 5.2 Symmetrised pair distance

`symmetrizedDistance` in `frontend/js/features/metrics.ts`:

```
function symmetrized(D, a, b):
    p := D[a].get(b)   ;; possibly absent
    q := D[b].get(a)   ;; possibly absent
    if p absent and q absent: return ∞
    if p absent: return q
    if q absent: return p
    return min(p, q)
```

### 5.3 Stress with optional layout-distance scaling

`computeStressFromAPSP` in `frontend/js/features/metrics.ts`:

```
function stress(V, P, D, σ):
    ;; V = list of nodes, P = positions (P[v] ∈ ℝ²),
    ;; D = APSP map, σ = layout-distance scale factor
    sumSq := 0
    reachable := 0
    unreachable := 0
    for i in 0..|V|-1:
        for j in i+1..|V|-1:
            d := symmetrized(D, V[i], V[j])
            if d = ∞:
                unreachable += 1
                continue
            ℓ := ‖P[V[i]] - P[V[j]]‖₂ / σ
            sumSq += (ℓ - d)²
            reachable += 1
    if reachable = 0: return (0, unreachable, 0)
    return (sumSq / reachable, unreachable, reachable)
```

**Normalisation variants.** Run with $\sigma \in \{1,\, \bar\ell,\, \sqrt{w^2+h^2},\, \sqrt{w \cdot h}\}$. The APSP $D$ is shared across all four runs.

### 5.4 Crossing detection + angle (M2)

`findCrossings` + `computeCrossingAngle` in `frontend/js/features/metrics.ts`:

```
function findCrossings(E):
    ;; E = list of edges with .source, .target ∈ ℝ² and
    ;;     .sourceId, .targetId, .type
    crossings := []
    for i in 0..|E|-1:
        a := E[i]
        for j in i+1..|E|-1:
            b := E[j]
            ;; skip pairs sharing a node — by definition can't cross
            if a.sourceId ∈ {b.sourceId, b.targetId}: continue
            if a.targetId ∈ {b.sourceId, b.targetId}: continue

            x := segment_intersection_point(a.source, a.target,
                                            b.source, b.target)
            if x = null: continue

            θ := arctan2(|cross(a, b)|, |dot(a, b)|)   ;; ∈ [0, π/2]
            (t₁, t₂) := lex_sort(a.type, b.type)
            crossings.append({ point: x, edgeA: a, edgeB: b,
                               angle: θ, edgeAType: t₁, edgeBType: t₂ })
    return crossings
```

where:

- $\mathrm{cross}(a, b) = (a_x \cdot b_y - a_y \cdot b_x)$ (the 2-D cross product as a scalar)
- $\mathrm{dot}(a, b) = (a_x \cdot b_x + a_y \cdot b_y)$
- $a, b$ in the cross/dot are the **direction vectors** $\vec{p_{\mathrm{tgt}}} - \vec{p_{\mathrm{src}}}$.

The absolute value on both arguments folds $\theta$ into $[0, \pi/2]$ (matches Huang-Eades-Hong's convention).

**Complexity.** $O(|E|^2)$ pair iteration; segment intersection is $O(1)$ per pair. See §4.9 for why we don't use Bentley-Ottmann.

### 5.5 M2 stats from a CrossingInfo list

`computeCrossingAngleStats`:

```
function angle_stats(crossings, τ = π/12):
    if crossings is empty: return (0, 0, 0)
    sum := 0; min := ∞; nearRight := 0
    for c in crossings:
        sum += c.angle
        if c.angle < min: min := c.angle
        if |c.angle - π/2| ≤ τ: nearRight += 1
    return (sum / |crossings|, min, nearRight / |crossings|)
```

Returns radians; UI converts to degrees.

### 5.6 Type-pair decomposition (M25)

`computeTypePairCrossingStats`:

```
function type_pair_stats(crossings):
    if crossings is empty: return ({}, "", 0)
    dist := empty map
    for c in crossings:
        key := c.edgeAType + "×" + c.edgeBType
        dist[key] := dist[key] + 1 (default 0)
    topLabel := ""; topCount := -1
    for (key, count) in dist:
        if count > topCount or (count = topCount and key < topLabel):
            topCount := count
            topLabel := key
    return (dist, topLabel, topCount / |crossings|)
```

Tie-break is lex-first on the label key — deterministic across runs.

### 5.7 Bridge chain_length accumulation (M19)

`hideNodeType` in `frontend/js/features/filter.ts`:

```
function hide_node_type(T):
    ;; T is the type to hide
    nodesToHide := { n ∈ V : type(n) = T }
    for n in nodesToHide:
        incomers := { p ∈ V : (p, n) ∈ E ∧ type(p) ∉ hidden_types }
        outgoers := { s ∈ V : (n, s) ∈ E ∧ type(s) ∉ hidden_types }
        for p in incomers:
            for s in outgoers:
                bridge_id := "typebridge_" + T + "_" + p.id + "_" + s.id
                if bridge_id ∉ existing_edges:
                    in_chain  := chain_length_of(edge p → n)   ;; 0 for original
                    out_chain := chain_length_of(edge n → s)   ;; 0 for original
                    chain_len := in_chain + 1 + out_chain
                    create_bridge(p, s, T, chain_len)
    remove_nodes(nodesToHide)
```

Where `chain_length_of(edge)` reads the edge's `chain_length` attribute (0 for non-bridge originals, $\ge 1$ for bridges).

**Worked example.** Hide CWE then TI on a chain `CVE → CWE → TI → VC`:

```
Step 1 (hide CWE):
   bridge CVE → TI created
   chain_len = 0 (CVE→CWE original) + 1 (CWE) + 0 (CWE→TI original) = 1

Step 2 (hide TI):
   bridge CVE → VC created
   chain_len = 1 (CVE→TI bridge from step 1) + 1 (TI) + 0 (TI→VC original) = 2
```

### 5.8 Edge consolidation ratio (M20)

`computeEcr` in `frontend/js/features/metrics.ts`:

```
function ecr(G):
    ;; visible = not exploit-hidden, not display:none
    per_parent := []
    for p in compound_parents(G):
        if p is not visible: skip
        children := { c : parent(c) = p ∧ c is visible }
        if children is empty: skip

        synthetic := |{ e : e incident on p ∧ e.synthetic ∧ e visible }|
        raw       := |{ e : e incident on some c in children
                            ∧ ¬e.synthetic
                            ∧ e.type ∉ {UNIT_EDGE, UNIT_EDGE_STD} }|
        per_parent.append((p.id, raw, synthetic, |children|))

    weight_sum := 0
    weighted   := 0
    for (id, raw, syn, n) in per_parent:
        if syn ≤ 0: continue   ;; ECR undefined; skip
        weighted   += (raw / syn) · n
        weight_sum += n
    return weighted / weight_sum if weight_sum > 0 else 0
```

**Why size-weighted.** A compound with 10 children that consolidates 30 edges into 3 (ECR=10) tells a stronger story than a compound with 2 children consolidating 6→3 (ECR=2). The weighting reflects per-edge consolidation faithfully: same total "consolidation per child" matters more than the average.

### 5.9 Compound cardinality (M21)

`computeCompoundCardinality`:

```
function compound_card(G):
    counts := empty map
    for n in visible_non_debug_nodes(G):
        p := parent(n)
        if p exists ∧ p is visible:
            counts[p.id] := counts[p.id] + 1 (default 0)

    return ({
        groupsCount: |counts|,
        largestGroupSize: max(counts.values, default=0),
        singletonFraction: |{c : counts[c] = 1}| / max(|counts|, 1),
        sizeDistribution: histogram(counts.values),
        groups: counts as list of (id, size)
    })
```

Singleton fraction is structurally 0 in the current merge implementation (CVEs never merged in groups <2). Kept as a regression sentinel.

---

## 6. Paper showcase plan — recommended evaluation procedure

The metrics tell a clean story when reductions are applied in this order. Each step removes more of the graph; the table reads top-to-bottom as a monotonically-improving sequence.

### Five-step pipeline

```
Step 1 — Baseline           (default sliders, all visible, no merge, no exploit paths)
Step 2 — Granularity        (tighten the relevant slider — e.g. CVE per HOST → CVE singular)
Step 3 — Hide internal types (hide CWE, hide TI — bridges materialise)
Step 4 — Merge by outcomes   (compound parents materialise)
Step 5 — Exploit Paths       (task-driven final filter)
```

**Why this order:**

| Choice | Rationale |
|--------|-----------|
| Granularity first | Pure structural change; sets a fair denominator for everything that follows |
| Visibility before merging | Visibility hides whole layers → fewer survivors to merge over → ECR numbers are honest |
| Exploit Paths last | Task-driven cut; putting it last makes reductions monotonic and the final graph self-explanatory |
| Each step removes one mechanism | "Contribution of mechanism $X$" = step ${X-1}$ value − step $X$ value, directly readable from the table |

### Headline evaluation table

Body-of-paper version. One row per step, six columns (plus optional graph identifier if showing multiple scans):

```
Step              |V|  |E|   C/E    M2 mean°  Stress*   ECR×   Top type pair
Baseline          N₀   E₀    0.36   42°       84.2      —      HAS_VULN×LEADS_TO
+ Granularity     N₁   E₁    0.31   45°       62.1      —      HAS_VULN×LEADS_TO
+ Hide CWE+TI     N₂   E₂    0.18   58°       38.5      —      HAS_VULN×ENABLES
+ Merge outcomes  N₃   E₃    0.09   71°       12.4      3.4×   IS_INSTANCE_OF×ENABLES
+ Exploit Paths   N₄   E₄    0.05   75°       8.1       3.4×   IS_INSTANCE_OF×ENABLES
```

(*Stress = `stress_per_pair_normalized_edge` × 1000 for readability)

### Numbers to highlight in prose

1. **C/E** — the most-cited GD readability metric. Should drop ~7× across the pipeline.
2. **M2 mean angle** — should rise toward 90° (residual crossings are increasingly orthogonal/structural).
3. **Stress (normalised)** — should drop monotonically; layout fits the smaller graph better.
4. **M20 ECR** — the *novelty* metric for the merge mechanism. Single number quantifies consolidation.
5. **M25 top type-pair label** — qualitative story. Different bottlenecks dominate at different steps; the label changing tells the reader what each mechanism resolved.
6. **M19 mean_contraction_depth** — should hit 2 after Step 3 (hiding two layers), confirming the bridge mechanism captured both hops.

### Appendix table

Same five rows, additional columns for completeness:

- M9 aspect_ratio
- M21 compound_groups_count, largest_group_size
- M19 bridge_edge_proportion, bridge_edge_count
- stress_unreachable_pairs, stress_reachable_pairs (so readers see the denominator changing)
- bbox_width, bbox_height (sanity check on normalisations)
- drawing_area, area_per_node

### Pitfalls explicitly addressed in the paper

1. **Don't compare raw `stress_per_pair` across graphs.** Always use a normalised variant; report `stress_reachable_pairs` alongside.
2. **Don't apply Exploit Paths before merge.** ECR is computed over visible CVEs; if exploit-paths pruned them already, M20 looks smaller than the mechanism's actual effect.
3. **Don't mix prereqs- and outcomes-merge in the same column.** Pick one for the body (outcomes is more compressive); discuss prereqs in the appendix.
4. **Be honest about M20 vs ATTACKER_BOX.** The implementation excludes ATTACKER_BOX (no synthetic edges) — `ecr_compounds_count` reports the actual denominator. Mention this in the table caption.
5. **Be honest about stress on merged graphs.** §4.3 caveat — `stress_unreachable_pairs` inflates after merge; reachable-pair stress is correct, side counter is noisy.

### Recommended paper structure for the evaluation section

1. **Single-graph walkthrough** (one example scan, e.g. nginx). Show the 5-step table, with a paired before/after image. Discuss each metric movement.
2. **Cross-corpus ablation** (all 9 example scans). Same 5 steps, report **mean ± std** of each metric per step. Strengthens the "this works generally" claim.
3. **Mechanism contribution attribution**. Difference table — for each metric, the contribution of each mechanism = step value − previous-step value. Identifies which mechanism is doing the work.
4. **Per-pair-typed-crossing illustration** (M25). At each step show the top-3 type pairs causing crossings; visualise this with the type-pair colouring overlay screenshots. This is unique to PAGDrawer's typed schema.
5. **Reproduction guide**. Exact UI sequence for re-running the pipeline (already in this document's procedural section above).

### UI procedure (reproducibility)

```
1. Upload Trivy scan → wait for enrichment to complete
2. Statistics → 📥 Export CSV  (Step 1: baseline row)
3. Settings → tighten relevant granularity slider → Apply
   Statistics → Export CSV       (Step 2)
4. Visibility: hide CWE → wait for re-layout
   Visibility: hide TI → wait for re-layout
   Statistics → Export CSV       (Step 3)
5. Merge popover → Merge by outcomes
   Statistics → Export CSV       (Step 4)
6. Exploit Paths toggle ON
   Statistics → Export CSV       (Step 5)
7. Concatenate the 5 CSVs in a spreadsheet, add a "step" column manually.
   Optionally also Export JSON at each step — captures the full settings snapshot
   for supplementary material.
```

The 📄 Export JSON variant captures the settings snapshot at each step too — useful as supplementary material so reviewers can verify the exact configuration that produced each row.

---

## 7. Things deferred / out of scope for the paper

Per [`Master_Implementation_Roadmap.md`](../Plans/Master_Implementation_Roadmap.md):

- **M22 (Attribute Compression Ratio)** — Stage 5. Predicts per-image reducibility; will appear in the appendix.
- **M26 (Edge-type Distribution)** — Stage 5. Per-edge-type count share; complements M25.
- **M3 (Angular Resolution at Nodes)** — Stage 6. Layout diagnostics.
- **M24 (Column Purity)** — Stage 6. Validates the typed schema renders faithfully.
- **M11, M12 (Neighbourhood Preservation, Trustworthiness)** — Stage 7. Topology-preservation story.
- **M14 (Reachability Preservation Rate)** — explicitly deferred. Requires a backend `/api/graph/full` reference graph; treated as future work.
- **M5, M8 (Edge length tinting, Bbox compactness shading)** — Stage 8 / post-umbrella. Surface treatments for figures.
- **User study** — out of scope per the Master roadmap. Mentioned in the limitation paragraph.

---

## References

> Purchase, H.C. (2002) — *Metrics for Graph Drawing Aesthetics.* JVLC 13(5), 501–516.
>
> Huang, W., Eades, P., Hong, S.-H. (2014) — *Larger crossing angles make graphs easier to read.* JVLC 25(4), 452–465.
>
> Kamada, T., Kawai, S. (1989) — *An algorithm for drawing general undirected graphs.* IPL 31(1), 7–15.
>
> Gansner, E.R., Koren, Y., North, S. (2004) — *Graph Drawing by Stress Majorization.* GD '04.
>
> Mooney, B. et al. (2024) — *Multi-Dimensional Landscape of Graph Drawing Metrics.*
>
> Machalewski et al. (2024) — *Expressing Impact of Vulnerabilities.* (the project's foundation paper)

Full per-metric source list lives in [`../Plans/metric_proposals.md`](../Plans/metric_proposals.md).
