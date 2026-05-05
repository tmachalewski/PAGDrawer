# 2026-05-04 → 2026-05-05 — Metrics roadmap, Stages 0–4

Two days of dense work. The umbrella branch `feature/metrics-roadmap` is at commit `728361a`, sitting **40 commits ahead of `main` and unpushed**. Test count went 159 → **302** on the frontend (no backend changes). Body-of-paper metric set complete.

This note covers what shipped, what didn't go to plan, and what's still outstanding before the umbrella merges to `main`.

---

## Stages completed

| # | Theme | Commit | Sub-branch |
|---|-------|--------|-----------|
| 0 | JSON export + settings snapshot | `b39da36` (merge) | `feature/metrics-roadmap-json-export` |
| 1 | Overlay extraction + M9 + M21 | `831c013` (merge) | `feature/metrics-roadmap-overlay-foundation` |
| 2 | M2 + M25 crossings refinement | `c33f48f` (merge) | `feature/metrics-roadmap-crossings` |
| 3 | M1 Stress + APSP helper | `5f76046` (merge) | `feature/metrics-roadmap-stress` |
| (3+) | Directed BFS + symmetrised stress + 3 normalisations + 2 visualisations | `754fde1` … `aa4cc08` | (umbrella direct) |
| 4 | M19 + M20 bridges and merges | `00f46fc` (merge) | `feature/metrics-roadmap-bridges-and-merges` |

Everything sits on the umbrella branch. Per the master roadmap, the umbrella merges to `main` after Stage 7 (Paper plan complete); Stage 8 is post-umbrella on a separate branch.

---

## Body-of-paper set complete

The "if you can implement five" tier from `Docs/Plans/metric_proposals.md` (minus M14 which we deferred):

| Metric | Status | Where |
|--------|--------|-------|
| **M1**  Stress | ✅ | raw + 3 normalisations (edge / diagonal / area) + visualisation overlays |
| **M2**  Crossing angle | ✅ | mean / min / right-angle ratio; HSL-by-angle dot colouring |
| **M20** Edge consolidation ratio | ✅ | size-weighted mean ECR; ECR×N suffix overlay on compounds |
| **M25** Type-pair crossings | ✅ | top pair share + label; categorical palette dot colouring |
| ~~M14~~ Reachability preservation | deferred per the Paper plan; needs a `/api/graph/full` reference graph and is its own sub-plan |

The paper draft can now report the headline evaluation table. Stages 5–7 fill out the appendix metrics.

---

## Stage 0 — JSON export + settings snapshot

Adds a `📄 Export JSON` button next to the existing CSV export. The JSON file carries:

- **The same metric values** as the CSV (one row equivalent, real numbers and nested objects)
- **A settings snapshot** — granularity per node type, visibility-hidden array, CVE merge mode, environment filter, exploit-paths active, layout name, force-refresh checkbox, skip_layer_2
- **Build provenance** — `git_sha` and `app_version` injected at build time via `vite.config.ts` so the file is traceable back to a specific commit
- **Data source** — every uploaded scan ID + name + vuln count, with a `selection_was_implicit` flag distinguishing "user picked all" from "user picked these specifically"

`schema_version: 1`. New keys are non-breaking; the version only bumps on rename/remove.

Files added:
- `frontend/js/config/buildInfo.ts` — reads injected build constants
- `frontend/js/features/settingsSnapshot.ts` — async helper that gathers state from 8 sources, each wrapped in try/catch with sensible defaults
- `frontend/js/features/metrics.ts` — `metricsToJSON`, `downloadMetricsJSON`, `buildMetricsJsonSnapshot`, `buildDataSourceSnapshot`

Two follow-up fixes after manual testing:
- `git_sha` and `app_version` were "unknown" at runtime — Vite's `define` does literal text replacement, but my `buildInfo.ts` was reading dynamically via `(import.meta as any)?.env?.[key]`. Switched to plain global identifiers (`__GIT_SHA__`, `__APP_VERSION__`) which Vite substitutes reliably.
- Renamed `exploit_paths_active` → `exploit_paths_only_active` (clearer: the flag is true when the user has "show only exploit paths" mode on).

---

## Stage 1 — Overlay extraction + M9 + M21

Refactor: ~170 LOC of inline overlay code in `statistics.ts` extracted into a new `frontend/js/ui/debugOverlay.ts` module with:

- `OverlayState` interface — 6 booleans (4 existing + M9 + M21) plus a `crossingsColorBy` radio mode
- 5 named presets: 🎯 crossings / 📐 layout / 🔗 reductions / ◌ defaults / ⊘ clear
- `localStorage` persistence under versioned key `debugOverlayState_v1`
- New `Debug Overlay Settings` modal with checkbox grid + preset row, reachable via a ⚙️ button next to the existing toggle

New metrics:
- **M9 Aspect Ratio** — `min(w, h) / max(w, h)` of bbox. Modal toggle adds `(AR = 0.42)` to the existing bbox label.
- **M21 Compound Group Cardinality (generalised)** — `largestGroupSize`, `singletonFraction`, `groupsCount`, full size→count distribution dict (JSON-only). Overlay appends `(×N)` to compound parent labels; idempotent so CVE_GROUP labels that already include the count don't double-up.

Singleton fraction stays at 0 in normal operation (CVE merge skips groups < 2 by construction). Kept as a regression sentinel.

---

## Stage 2 — M2 + M25 crossings refinement

Both extend the existing `findCrossings()` so each `CrossingInfo` now carries:
- `angle` (radians, `arctan2(|cross|, |dot|)`, in `[0, π/2]`)
- `edgeAType`, `edgeBType` (lex-sorted so `(A,B)` and `(B,A)` collapse to one bucket)

Computed scalars:
- **M2** — `crossings_mean_angle_deg`, `crossings_min_angle_deg`, `crossings_right_angle_ratio` (within ±15° of 90° per Huang/Eades/Hong 2014)
- **M25** — `crossings_top_pair_share`, `crossings_top_pair_label`; full per-pair distribution in JSON-only `crossings_type_pair_distribution`

Conflict resolution: M2 and M25 share the same red dot. New radio in the Debug Overlay modal — `Crossings color dots by`: `none` / `angle` (red→yellow→green by acuteness) / `typePair` (10-color categorical palette ordered by frequency).

CSV gains 5 columns; the dict-shaped distribution is JSON-only (variable cardinality would break stable headers). Top-pair label is RFC 4180-quoted when needed.

---

## Stage 3 — M1 Stress

The most-cited graph-drawing layout-quality metric. Reviewers expect it. Expanded into a substantial subsystem.

### Algorithm

PAGDrawer's edges are unweighted, so BFS computes single-source shortest paths in `O(|V| + |E|)`. Naming functions after Dijkstra/Bellman-Ford/Floyd-Warshall would suggest weighted machinery the metric doesn't need. Total APSP cost: `O(|V| · (|V| + |E|))`.

### Directed graph adaptation

PAGDrawer's graph is directed (attack graph DAG: ATTACKER → HOST → ... → VC, plus ENABLES back-edges). Initial implementation used undirected adjacency, which gave wrong distances for unreachable directed pairs.

Switched to **directed BFS** + **symmetrised distance** for stress: `d_ij = min(d(i→j), d(j→i))`, undefined if neither direction has a path. Euclidean is symmetric → graph-side comparison must be too. Documented in detail in **`Docs/_domains/StressMetric.md`** (NEW, ~250 lines covering the three options, why we picked symmetrised, BFS vs Dijkstra, edge cases, normalisations, visualisations, references).

### Three normalisations

Raw stress mixes Euclidean distances with hop counts; not comparable across graphs. Added three normalised variants where layout distance is divided by a length scale before squaring:

| Field | Scale | Convention |
|-------|-------|-----------|
| `stress_per_pair_normalized_edge` | mean edge length | Kamada-Kawai |
| `stress_per_pair_normalized_diagonal` | √(w² + h²) (bbox diagonal) | Mooney 2024 |
| `stress_per_pair_normalized_area` | √(w · h) (geometric mean of sides) | drawing-area variant |

All three reuse a single APSP. Per-pair iteration is O(|V|²) and trivial.

### Visualisations

Two separate toggles in the Debug Overlay modal under **"Stress visualisation (M1)"**:

1. **Color nodes by graph distance from clicked source** — click any node, every reachable node recolors red→yellow→green by symmetrised distance; unreachable greys out; source gets a yellow border.
2. **Show pair distances on click** — click two nodes, an upper-right floating panel shows directed distances both ways, the symmetrised distance, and the Euclidean distance.

Both modes click-driven, not render-driven. Took several iterations to get the listener binding right — final solution uses direct handler-reference binding (no Cytoscape namespace), bound on every Statistics-modal refresh as the most reliable rebind point.

### Bbox dimensions exposed

Added `bbox_width`, `bbox_height` to CSV/JSON/modal alongside the existing `drawing_area`. Cheap (the bbox is already computed for the diagonal/area normalisations and the M9 aspect ratio overlay) and useful for sanity-checking the normalised stress values.

### Compound-node behaviour documented (not changed)

Stress on a graph with `merge by outcomes` active sees compound parents AND their children-with-hidden-edges. The unreachable-pair count inflates by the number of children × everything-else, but reachable pairs compute correctly. Documented in `StressMetric.md` § "Behaviour with compound nodes" — known limitation, intentionally not fixed in this iteration. Cleanest future fix is a "node has at least one visible edge" filter that handles both outcomes-merge and prereqs-merge correctly.

---

## Stage 4 — M19 + M20 bridges and merges

The plan called for **backend** chain_length tracking. **Bridge edges are entirely frontend** — created by `hideNodeType` in `filter.ts` when the user toggles visibility. So no Python changes needed. The plan was wrong about this; saved a chunk of work.

### M19 — Bridge contraction depth

`filter.ts` now records `chain_length` on every bridge edge it creates. New `readChainLength()` helper inspects the existing pred→node and node→succ edges; when either is itself a bridge from a prior `hideNodeType` call, its chain_length is summed in. Accumulates correctly across chained hides:

```
hide CWE  → bridges CVE→TI carry chain_length=1
hide TI   → bridges CVE→VC carry chain_length=2
            (= CVE→TI bridge chain (1) + 1 for TI itself + TI→VC original (0))
```

Verified end-to-end via temporary console-logging during testing.

Reported scalars: `bridge_edge_proportion`, `mean_contraction_depth`, `bridge_edge_count`. JSON also carries the full `bridge_chain_length_distribution` dict.

Overlay: new `bridgeChainDepth` toggle. Renders `k=N` labels at the midpoint of every bridge with chain_length > 0.

### M20 — Edge consolidation ratio

For each compound parent: `ECR = raw_edges / synthetic_edges`. Aggregated as a size-weighted mean across compounds with synthetic edges (excludes ATTACKER_BOX, prereqs-mode merge, unmerged compounds).

Reported: `mean_ecr_weighted`, `ecr_compounds_count`. JSON carries per-parent breakdown in `ecr_per_compound`.

Overlay: new `edgeConsolidationRatio` toggle. Composes with M21:
- M21 alone → `Outcome XYZ  (×5)`
- M20 alone → `Outcome XYZ  (ECR×3.4)`
- Both → `Outcome XYZ  (×5  ECR×3.4)`
- CVE_GROUP whose backend label already has `(×N)` → `Outcome (×5)  (ECR×3.4)`

Refactored `applyGroupCardinalityBadges` → `applyCompoundLabelAnnotations` to handle both modes in a single pass, one save-original per parent.

`reductions` preset updated to enable M21 + M19 + M20 (the reduction-transparency triad).

### Visibility fix (728361a)

User caught a bug post-Stage-4: exploit-hidden compound parents were appearing in the JSON download. Both `computeEcr()` and `computeCompoundCardinality()` walked `cy.nodes(':parent')` / `n.parent()` without checking visibility. Fix: skip parents with `.exploit-hidden` class or `display: none`; for surviving parents, only count visible children.

---

## What didn't go to plan

### Crossing-dot hover hint — 6 attempts before working

Wanted a small `<angle>°  <typePair>` hint when the user hovers a crossing dot. Cytoscape's selector-delegation kept failing (`tap.namespace` listener bound but never fired). Tried:

1. `.hovered` class on the dot, `data(hoverLabel)` mapper in stylesheet — didn't render
2. Inline `node.style({...})` toggled on hover/mouseout — same
3. Click instead of hover (toggle behaviour) — same
4. `events: 'yes'` forced inline at `cy.add` time — same
5. Per-dot tap listener (no delegation) — same
6. Reuse the **existing tooltip system** — works

Pattern recognised: the standard tooltip handlers in `tooltip.ts` use direct handler references, not namespaces. They've worked for years on every regular node. Just needed to relax the debug-overlay-node guard to let crossing dots through. Six commits in the chain (`94b29a9` → `cba11f3`); kept as separate commits in history per user preference rather than squashing.

This pattern then helped with Stage 3's stress-vis listener — went straight to direct-handler-reference binding.

### Backend work for M19 — wasn't actually needed

Master roadmap and the daughter plan both assumed bridge edges were a backend concept. They're entirely frontend (`filter.ts`). Saved the round trip through `src/graph/builder.py` + API + tests. Mentioned in the Stage 4 commit body so the deviation is traceable.

### Sub-branch separator collision

Initial plan used `feature/metrics-roadmap/<stage>` for sub-branches, but git can't host both `feature/metrics-roadmap` (umbrella) and `feature/metrics-roadmap/foo` (sub) — the slash makes them conflicting refs. Switched to single hyphen: `feature/metrics-roadmap-<stage>`. Documented in the Master roadmap.

---

## Test count

| Suite | Before | After | Delta |
|-------|--------|-------|-------|
| Frontend (Vitest) | 159 | **302** | +143 |
| Backend (pytest) | 381 | 381 | 0 |
| **Grand total** | 540 | **683** | +143 |

TS typecheck clean on every touched file throughout. Pre-existing errors in unrelated test files remain.

---

## Outstanding work

| Stage | Metrics | Effort estimate |
|-------|---------|-----------------|
| 5 | M22 + M26 paper-appendix essentials (incl. `mergeKeys.ts` extraction) | small |
| 6 | M3 + M24 layout diagnostics | medium (overlay-heavy) |
| 7 | M11 + M12 topology preservation (reuses M1 APSP) | medium |
| 8 | M5 + M8 surface treatments (post-umbrella) | small |

Plus operational:
- **Push the umbrella to `origin`** — 40 commits unpushed locally; safety net
- **Optional rebase / squash** — failed-attempt commits (the 6-step crossing hint debug, the 4-step stress-vis listener debug) are kept verbatim in history; could be squashed before main merge if the user prefers a tidier log

---

## Files affected

### New
- `frontend/js/config/buildInfo.ts` + tests
- `frontend/js/features/settingsSnapshot.ts` + tests
- `frontend/js/ui/debugOverlay.ts` + tests
- `Docs/_domains/StressMetric.md`

### Modified — major
- `frontend/js/features/metrics.ts` — 12 new metric computations + helpers + 2 export formats
- `frontend/js/features/metrics.test.ts` — 78 → 145+ tests
- `frontend/js/features/filter.ts` — `chain_length` accumulation
- `frontend/js/ui/statistics.ts` — modal table, JSON button, scan-selection-aware data-source snapshot, stress-vis re-bind hook
- `frontend/index.html` — debug overlay modal, stress-pair panel, JSON button
- `frontend/css/styles.css` — debug overlay modal + stress-pair panel
- `frontend/vite.config.ts` — `__GIT_SHA__` + `__APP_VERSION__` injection

### Modified — minor
- `frontend/js/ui/tooltip.ts` — relax debug-overlay guard for crossing dots
- `frontend/js/config/constants.ts` — `events: 'yes'` on crossing dots
- `Docs/_domains/StatisticsModal.md` — full schema + overlay catalogue
- `Docs/_domains/DrawingQualityMetrics.md` — per-metric sections for everything new
- `Docs/Plans/JSON_Export_With_Settings.md`, `Master_Implementation_Roadmap.md`, `Paper_Evaluation_Metrics.md`, `Debug_Overlay_Visualizations.md` — reflect actual implementation
