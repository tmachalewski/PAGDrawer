# PAGDrawer - Project State Overview

**Date:** 2026-05-03
**Version:** 2.1.0 (first public release on GitHub)
**Test Coverage:** 381 Python tests + 159 TypeScript unit tests = **540 total**
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

---

## Architecture Overview

(Tech stack and directory layout unchanged from v2.0.0; see `2026-04-20-15-55-Project_State_Overview.md` for the full layout.)

### Tech Stack

| Layer        | Technology                       | Port  |
| ------------ | -------------------------------- | ----- |
| Backend      | Python 3.10 + FastAPI + NetworkX | 8000  |
| Frontend     | TypeScript + Vite + Cytoscape.js | 3000  |
| Persistence  | MongoDB 7 (Docker)               | 27017 |
| Testing      | pytest + Playwright + Vitest     | -     |

---

## Recent Changes (2026-04-20 → 2026-05-03)

### Public release

- Pushed to https://github.com/tmachalewski/PAGDrawer
- Apache 2.0 license
- README with UI screenshot + before/after SVG pair
- Renamed local default branch `master` → `main`
- All 13 historical feature branches pushed alongside `main`

### Project-name correction

The expansion of PAGDrawer is **Probabilistic Attack Graph Drawer**. Three stale labels updated:
- `README.md`
- `frontend/index.html` `<title>` and logo subtitle
- This series of project-status docs (going forward)

### Bug fixes

| Fix | Description |
|-----|-------------|
| Bridge nodes in Exploit Paths | `INSIDE_NETWORK` was hidden when both Exploit Paths and skip_layer_2 were active. Always-include `[?is_phase_separator]` in the visible set. |
| Merge × exploit-hidden | An empty "no VCs" compound stranded at (0, 0) when merging while Exploit Paths was active. Filter out `exploit-hidden` CVEs before grouping. |

### New metrics columns

Three new entries in the Statistics modal and the CSV export:

| Column | What |
|--------|------|
| `area_per_node` | `drawing_area / |V|` — easier to compare across reduction steps than raw area |
| `unique_cves` | distinct base CVE IDs in the live graph (`:dN` / `@...` suffixes stripped) |
| `trivy_vuln_count` | sum of Trivy-reported per-package vulnerability entries across all uploaded scans |

CSV header is now:
```
nodes,edges,unique_cves,trivy_vuln_count,crossings_raw,crossings_normalized,crossings_per_edge,drawing_area,area_per_node,edge_length_cv
```

### Example artifacts

`examples/` now contains per-scan subdirectories with SVG graph exports and metrics CSVs from running the app against:

`alpine_edge`, `busybox`, `memcached_trixie`, `nginx_stable-trixie-perl`, `node_iron-alpine3_22`, `postgres_15_17-alpine3_22`, `python_latest`, `redis_7_4_8-alpine3_21`, `ubuntu_resolute-20260413`.

Plus the underlying scan JSONs and an expanded `examples/trivyscangeneration.txt` with Docker Hub URLs and the commands to regenerate every example.

### UI

Top-of-page UI screenshot in the README at `examples/_UI/UI 2026-04-21 183058.jpg`.

---

## Test Coverage (current)

| Suite | Count | Framework |
|-------|-------|-----------|
| `test_builder.py` | ~84 | pytest |
| `test_api_endpoints.py` | ~30 | pytest |
| `test_frontend.py` | ~90 | pytest-playwright |
| `test_nvd_fetcher.py` | 24 | pytest |
| `test_cwe_fetcher.py` | 48 | pytest |
| `test_mongo_client.py` | 16 | pytest |
| `test_jobs.py` | 17 | pytest |
| `test_schema.py` | ~20 | pytest |
| **Backend total** | **381** | |
| TypeScript unit tests (Vitest) | **159** | |
| **Grand total** | **540** | |

---

## Known Limitations

(Carried over from v2.0.0 + a small addition.)

1. **Mongo is required** — no offline / file-cache fallback
2. **First rebuild is slow** — NVD rate-limits at 6 s/CVE; 500 CVEs ≈ 50 min
3. **Cancel lag** — cancellation is checked between CVEs, so up to 6 s delay
4. **No persistence for graph config** — resets on backend restart
5. **Single-user** — no multi-user / auth
6. **Browser-only** — no desktop/mobile apps
7. **`trivy_vuln_count` reflects all uploaded scans**, not just the ones in the current rebuild — backend doesn't expose per-rebuild scan IDs yet
8. **`STATIC_CWE_MAPPING` deactivated** — every CWE goes through MITRE REST API; TODO to re-enable after validation

---

## Deferred / TODO

- **Phase D** of MongoDB persistence — global "Refresh all NVD data" button in Settings (per-rebuild force-refresh checkbox already works)
- **Re-enable `STATIC_CWE_MAPPING`** after comparing live REST-sourced impacts against the in-code constant
- **Auto-purge old jobs on startup** (`JobManager.purge_old_jobs(3600)` in the FastAPI startup event)
- **NVD API key wiring** through config / env var for higher rate limits
- **Tighten `trivy_vuln_count`** to scans actually contributing to the current graph

---

## Research Foundation

> **Machalewski et al. (2024)** — *Expressing Impact of Vulnerabilities*
> Consensual Transformation Matrix from expert consensus on 22 CVEs,
> mapping 24 Technical Impact categories to Vector Changer privilege states.

Drawing-quality metrics:

> **Purchase, H.C. (2002)** — *Metrics for Graph Drawing Aesthetics.*
> Journal of Visual Languages and Computing, 13(5), 501–516.
