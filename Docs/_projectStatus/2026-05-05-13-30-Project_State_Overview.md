# PAGDrawer - Project State Overview

**Date:** 2026-05-05
**Version:** 2.1.0 (first public release on GitHub) — metrics work in progress on `feature/metrics-roadmap`
**Test Coverage:** 381 Python tests + **302 TypeScript unit tests** = **683 total**
**Repository:** https://github.com/tmachalewski/PAGDrawer (Apache 2.0)

---

## Quick Start

```bash
# Prerequisite: Docker (for MongoDB)
bash Scripts/start-mongo.sh

# Backend (FastAPI on :8000) — fails fast if Mongo unreachable
bash Scripts/start-backend.sh

# Frontend (Vite dev server on :3000)
bash Scripts/start-frontend.sh

# Stop
bash Scripts/kill-backend.sh
bash Scripts/kill-frontend.sh
bash Scripts/kill-mongo.sh   # data persists in pagdrawer_mongodb_data volume

# Tests
PAGDRAWER_SKIP_MONGO=1 python -m pytest tests/ -v
cd frontend && npm run test
```

---

## What is PAGDrawer?

**PAGDrawer** (**Probabilistic Attack Graph Drawer**) transforms vulnerability scan data into interactive attack graphs. It models how attackers exploit CVEs to escalate privileges and move laterally through networks.

Based on **Machalewski et al. (2024)** — "Expressing Impact of Vulnerabilities", implementing the **Consensual Transformation Matrix** for mapping technical impacts to privilege changes.

GD 2026 paper draft underway; the metrics work documented below is the evaluation backbone.

---

## Recent changes (2026-05-03 → 2026-05-05)

### Metrics roadmap — Stages 0–4 of 8 done

Two days of dense work on `feature/metrics-roadmap` (umbrella branch, **40 commits unpushed**). Body-of-paper metric set complete: **M1, M2, M20, M25** all in CSV / JSON.

Per-stage summary (full detail in `Docs/_dailyNotes/2026-05-05-13-30-Metrics_Roadmap_Stages_0_to_4.md`):

| Stage | Theme | Status |
|-------|-------|--------|
| **0** | JSON export + settings snapshot + git-SHA build provenance | ✅ |
| **1** | Overlay extraction into `debugOverlay.ts` + M9 + M21 | ✅ |
| **2** | M2 (crossing angle) + M25 (type-pair crossings) | ✅ |
| **3** | M1 Stress + APSP helper (directed BFS, symmetrised, 3 normalisations, 2 visualisations) | ✅ |
| **4** | M19 (bridge contraction depth) + M20 (edge consolidation ratio) | ✅ |
| 5 | M22 + M26 paper-appendix essentials | next |
| 6 | M3 + M24 layout diagnostics | pending |
| 7 | M11 + M12 topology preservation | pending |
| 8 | M5 + M8 surface treatments (post-umbrella) | pending |

### Statistics modal extensions

The Drawing Quality table now reports:

| Field | Source |
|-------|--------|
| `stress_per_pair` + 3 normalisations (`_normalized_edge`, `_normalized_diagonal`, `_normalized_area`) | M1, Purchase 2002 / Kamada-Kawai |
| `stress_unreachable_pairs`, `stress_reachable_pairs` | skip-and-report convention |
| `crossings_mean_angle_deg`, `crossings_min_angle_deg`, `crossings_right_angle_ratio` | M2, Huang-Eades-Hong 2014 |
| `crossings_top_pair_share`, `crossings_top_pair_label` | M25 |
| `aspect_ratio` | M9 |
| `compound_groups_count`, `compound_largest_group_size`, `compound_singleton_fraction` | M21 |
| `bridge_edge_proportion`, `mean_contraction_depth`, `bridge_edge_count` | M19 |
| `mean_ecr_weighted`, `ecr_compounds_count` | M20 |
| `bbox_width`, `bbox_height` | (sanity-checking the normalisations) |

CSV header is now ~32 columns. JSON export at schema v1 carries the same numeric values plus four variable-cardinality dicts (compound size distribution, type-pair crossing distribution, bridge chain-length distribution, per-compound ECR breakdown).

### New `📄 Export JSON` button

Sits next to the existing CSV export. Adds:
- **Settings snapshot** — every user-controllable input that affects the metrics (granularity, visibility, merge mode, env filter, exploit paths, layout, …)
- **Build provenance** — `git_sha` + `app_version` injected at build time via Vite, so each export is traceable to a specific commit
- **Data source** — uploaded scan list filtered to the current scan-selector choice, with `selection_was_implicit` flag

Schema version v1; new metric fields are non-breaking additions.

### New Debug Overlay Settings modal

Per-overlay toggles (10 total) replacing the previous all-or-nothing button. Five named presets:
- 🎯 Crossings analysis — M25 type-pair coloured dots + aspect ratio
- 📐 Layout diagnostics — bbox + mean / std-dev edges + aspect ratio
- 🔗 Reduction transparency — M21 group sizes + M19 chain-depth labels + M20 ECR
- ◌ Defaults — original 4 overlays
- ⊘ Clear all

State persists in `localStorage` under versioned key `debugOverlayState_v1`.

### Documentation

Two new domain docs:
- **`Docs/_domains/StressMetric.md`** — covers what stress measures, the directed-graph adaptation (three options + chosen one), why BFS over Dijkstra/Bellman-Ford/Floyd-Warshall, edge cases, normalisations, visualisations, references
- Significantly expanded `Docs/_domains/DrawingQualityMetrics.md` — per-metric sections for M1, M2, M9, M19, M20, M21, M25
- Significantly expanded `Docs/_domains/StatisticsModal.md` — full overlay catalogue, modal-mockup with all 10 toggles, JSON schema example

### Bugfixes during testing

| Fix | Description |
|-----|-------------|
| Vite `define` for `git_sha` | Plain global identifiers (`__GIT_SHA__`) work; nested `import.meta.env.VITE_*` paths weren't substituted by `define`'s text replacement when accessed via dynamic key |
| Crossing dot click not firing | Six attempts before settling on reusing the standard tooltip system (direct handler refs, no namespace) |
| Stress vis listener not firing on persisted state | Bind on every Statistics-modal refresh, not just on `setOverlayState` |
| Stress vis cleared on unrelated overlay toggles | Decoupled stress-vis lifecycle from `redraw()` — `clearAll()` no longer touches stress state |
| Exploit-hidden compounds in metrics download | Both `computeEcr` and `computeCompoundCardinality` now skip parents with `.exploit-hidden` class or `display: none`; only count visible children |
| Scan selection not respected in JSON | `data_source.scans_in_current_graph` now filtered to user's scan-selector pick; `selection_was_implicit` flag distinguishes "all" from "specific" |

---

## Architecture Overview

(Tech stack, ports, and directory layout unchanged from v2.0.0; see `2026-04-20-15-55-Project_State_Overview.md` for the full layout.)

### Tech Stack

| Layer        | Technology                       | Port  |
| ------------ | -------------------------------- | ----- |
| Backend      | Python 3.10 + FastAPI + NetworkX | 8000  |
| Frontend     | TypeScript + Vite + Cytoscape.js | 3000  |
| Persistence  | MongoDB 7 (Docker)               | 27017 |
| Testing      | pytest + Playwright + Vitest     | -     |

### New frontend modules added during the metrics work

| File | Role |
|------|------|
| `frontend/js/config/buildInfo.ts` | Reads `__GIT_SHA__` / `__APP_VERSION__` injected by `vite.config.ts` |
| `frontend/js/features/settingsSnapshot.ts` | Async helper that gathers state from 8 sources for the JSON export |
| `frontend/js/ui/debugOverlay.ts` | Per-overlay state machine, drawing pipeline, modal wiring, stress visualisations |

### Modules with significant additions

- `frontend/js/features/metrics.ts` — 12 new metric computations, the APSP helper, two export serializers, all the M19/M20/M21 helpers
- `frontend/js/features/filter.ts` — `chain_length` accumulation on bridge edges
- `frontend/vite.config.ts` — build-time identifier injection
- `frontend/js/ui/statistics.ts` — modal table extensions, JSON button wiring, stress-vis listener rebind hook
- `frontend/js/ui/tooltip.ts` — relaxed debug-overlay guard for crossing dots

---

## Test Coverage (current)

| Suite | Count | Framework | Notes |
|-------|-------|-----------|-------|
| `test_builder.py` | ~84 | pytest | unchanged |
| `test_api_endpoints.py` | ~30 | pytest | unchanged |
| `test_frontend.py` | ~90 | pytest-playwright | unchanged |
| `test_nvd_fetcher.py` | 24 | pytest | unchanged |
| `test_cwe_fetcher.py` | 48 | pytest | unchanged |
| `test_mongo_client.py` | 16 | pytest | unchanged |
| `test_jobs.py` | 17 | pytest | unchanged |
| `test_schema.py` | ~20 | pytest | unchanged |
| **Backend total** | **381** | | |
| TypeScript unit tests (Vitest) | **302** | | up from 159 (+143 from the metrics work) |
| **Grand total** | **683** | | |

TS typecheck clean on every touched file. Pre-existing errors in unrelated test files remain.

---

## Known Limitations

(Carried over from v2.1.0 + additions from the metrics work.)

1. **Mongo is required** — no offline / file-cache fallback
2. **First rebuild is slow** — NVD rate-limits at 6 s/CVE; 500 CVEs ≈ 50 min
3. **Cancel lag** — cancellation is checked between CVEs, so up to 6 s delay
4. **No persistence for graph config** — resets on backend restart
5. **Single-user** — no multi-user / auth
6. **Browser-only** — no desktop/mobile apps
7. **`STATIC_CWE_MAPPING` deactivated** — every CWE goes through MITRE REST API; TODO to re-enable after validation
8. **Stress on merged graphs has noisy unreachable count** — outcomes-merge hides children's edges and prereqs-merge leaves parents disconnected; either way, the unreachable-pair counter inflates by `|merged children| · (|V| − |merged children|)`. Documented in `StressMetric.md` § "Behaviour with compound nodes" — known limitation, not fixed in this iteration.
9. **Stress visualisation is fresh APSP per click** — no within-modal cache yet. Sub-second for typical PAGDrawer graphs but will become noticeable at large `|V|`. Cleanest future fix is a `(visibleNodeIds, visibleEdgeIds)`-keyed cache that M11/M12 can also share when they ship in Stage 7.
10. **`trivy_vuln_count` uses scan-selector pick** (was: all uploaded scans). Fixed during Stage 0; the older-version note in v2.1.0 status is now obsolete.

---

## Deferred / TODO

### Operational
- **Push `feature/metrics-roadmap` to origin** — 40 commits unpushed; safety net
- **Re-enable `STATIC_CWE_MAPPING`** after comparing live REST-sourced impacts against the in-code constant
- **Auto-purge old jobs on startup** (`JobManager.purge_old_jobs(3600)` in the FastAPI startup event)
- **NVD API key wiring** through config / env var for higher rate limits
- **Phase D** of MongoDB persistence — global "Refresh all NVD data" button in Settings

### Metrics roadmap (Stages 5–8)
- **Stage 5 — M22 + M26**, paper-appendix essentials. Includes extracting `mergeKeys.ts` from `cveMerge.ts` so M22 (Attribute Compression Ratio) and the merge logic share the same key function. M26 (Edge-Type Distribution) ships as flat per-edge-type CSV columns sourced from the edge-type enum.
- **Stage 6 — M3 + M24**, layout diagnostics. M3 (Angular Resolution at Nodes) with arc-overlay for narrow gaps. M24 (Column Purity) with halo overlay for nodes outside their dagre column.
- **Stage 7 — M11 + M12**, topology preservation. Both reuse M1's APSP. M11 (k-NN Preservation) and M12 (Trustworthiness & Continuity) — closes the dimension-reduction-style story for the appendix.
- **After Stage 7** — umbrella merges to `main`. Stage 8 (M5 edge length deviation tint, M8 bbox compactness shading) ships post-umbrella on a separate branch.

### Stress-related polish (deferred)
- Within-modal APSP cache (M11/M12 will share it)
- Visible-edge filter for stress (cleanest fix for the merge-noise issue)
- Stress-vis "click two nodes to compare" panel could become a richer side-panel showing the full hop-by-hop path

---

## Research Foundation

> **Machalewski et al. (2024)** — *Expressing Impact of Vulnerabilities*
> Consensual Transformation Matrix from expert consensus on 22 CVEs,
> mapping 24 Technical Impact categories to Vector Changer privilege states.

Drawing-quality metrics:

> **Purchase, H.C. (2002)** — *Metrics for Graph Drawing Aesthetics.*
> Journal of Visual Languages and Computing, 13(5), 501–516.

> **Huang, W., Eades, P. and Hong, S.-H. (2014)** — *Larger crossing angles make graphs easier to read.*
> Journal of Visual Languages and Computing, 25(4), 452–465.

> **Kamada, T. and Kawai, S. (1989)** — *An algorithm for drawing general undirected graphs.*
> Information Processing Letters, 31(1), 7–15.

> **Gansner, E.R., Koren, Y. and North, S. (2004)** — *Graph Drawing by Stress Majorization.*
> International Symposium on Graph Drawing.

> **Mooney, B. et al. (2024)** — *Multi-Dimensional Landscape of Graph Drawing Metrics.*
> (recent ten-metric panel, used as a sanity reference for the normalisation choices)

Full per-metric source list lives in `Docs/Plans/metric_proposals.md`.
