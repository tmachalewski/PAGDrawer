# PAGDrawer - Project State Overview

**Date:** 2026-04-20
**Version:** 2.0.0 (MongoDB hard dependency added)
**Test Coverage:** ~381 Python tests + 156 TypeScript unit tests = ~537 total

---

## Quick Start

```bash
# Start MongoDB (required; Docker)
bash Scripts/start-mongo.sh

# Backend (FastAPI on port 8000) — fails fast if Mongo unreachable
bash Scripts/start-backend.sh

# Frontend (Vite dev server on port 3000)
bash Scripts/start-frontend.sh

# Stop
bash Scripts/kill-backend.sh
bash Scripts/kill-frontend.sh
bash Scripts/kill-mongo.sh   # data persists in pagdrawer_mongodb_data volume

# Run all tests (PAGDRAWER_SKIP_MONGO=1 skips the startup ping in isolated runs)
PAGDRAWER_SKIP_MONGO=1 python -m pytest tests/ -v
cd frontend && npm run test
```

---

## What is PAGDrawer?

**PAGDrawer** (Privilege-based Attack Graph Drawer) transforms vulnerability scan data into interactive attack graphs. It models how attackers exploit vulnerabilities to escalate privileges and move laterally through networks.

Based on **Machalewski et al. (2024)** - "Expressing Impact of Vulnerabilities", implementing the **Consensual Transformation Matrix** for mapping technical impacts to privilege changes.

---

## Architecture Overview

### Tech Stack

| Layer        | Technology                       | Port  |
| ------------ | -------------------------------- | ----- |
| Backend      | Python 3.10 + FastAPI + NetworkX | 8000  |
| Frontend     | TypeScript + Vite + Cytoscape.js | 3000  |
| Persistence  | MongoDB 7 (Docker)               | 27017 |
| Testing      | pytest + Playwright + Vitest     | -     |

### Directory Structure

```
PAGDrawer/
├── docker-compose.yml           # NEW: Mongo service + volume
├── .env.example                 # NEW: MONGODB_URI template
├── src/
│   ├── core/
│   ├── data/
│   │   ├── mongo_client.py      # NEW: singleton + TTL helpers
│   │   ├── jobs.py              # NEW: rebuild JobManager
│   │   └── loaders/             # NVDFetcher/CWEFetcher -> MongoDB
│   ├── graph/builder.py
│   └── viz/app.py               # rebuild endpoint is now async (background)
├── frontend/
│   └── js/features/
│       ├── metrics.ts           # NEW: drawing quality metrics
│       ├── rebuildProgress.ts   # NEW: polling + progress bar
│       ├── cveMerge.ts
│       ├── environment.ts
│       └── ...
├── Scripts/
│   ├── start-mongo.sh           # NEW
│   ├── kill-mongo.sh            # NEW
│   ├── start-backend.sh
│   └── ...
├── tests/
│   ├── test_mongo_client.py     # NEW: 16 tests
│   ├── test_jobs.py             # NEW: 17 tests
│   └── ...
└── Docs/
    ├── _dailyNotes/             # development logs
    ├── _projectStatus/          # this file
    ├── _domains/                # domain docs
    └── Plans/                   # planning docs
```

---

## Core Concept: The Attack Graph

(unchanged from v1.8.0 — see `2026-04-11-14-28-Project_State_Overview.md` for
full node-type and edge-type tables and the chain-depth-aware flow.)

### Node types (9)

ATTACKER, HOST, CPE, CVE, CWE, TI, VC, BRIDGE, CVE_GROUP

### Edge types (9)

ENTERS_NETWORK, CAN_REACH, RUNS, HAS_VULN, IS_INSTANCE_OF, HAS_IMPACT, LEADS_TO, ENABLES, HAS_STATE

---

## Key Features

### Data Persistence (NEW in v2.0)

| Collection      | TTL      | Populated by                        |
| --------------- | -------- | ----------------------------------- |
| `nvd_cves`      | 7 days   | `NVDFetcher` on each CVE lookup     |
| `epss_scores`   | 7 days   | `NVDFetcher.fetch_epss` + batch     |
| `cwe_impacts`   | 30 days  | `CWEFetcher` from MITRE REST API    |
| `rebuild_jobs`  | soft 1 h | `JobManager` during rebuilds        |

- TTL is enforced in Python code (not MongoDB TTL index) — stale records remain queryable
- Fail-fast on startup if Mongo is unreachable
- `STATIC_CWE_MAPPING` in-code dict is gated behind `USE_STATIC_MAPPING = False` (TODO: re-enable after validating live source)
- See `_domains/MongoDBPersistence.md` for the architecture

### Background Rebuild Jobs (NEW in v2.0)

- `POST /api/data/rebuild` returns `{status: "started", job_id}` immediately
- Worker runs in a Python `threading.Thread` (so the event loop stays responsive)
- `GET /api/data/rebuild/progress/{job_id}` exposes phase/current CVE/N-of-total
- `POST /api/data/rebuild/cancel/{job_id}` requests cancellation
- 409 Conflict if another job is already running
- Frontend polls every 500 ms; progress bar in the data source panel

### CVE Merge Modes (from v1.8)

Two merge strategies when CWE+TI are hidden: by prerequisites (AV/AC/PR/UI) or by outcomes (VC states). Layer-aware keys prevent L1/L2 cross-merging. Compound nodes keep children hoverable.

### Drawing Quality Metrics (NEW)

Statistics modal exposes three Purchase (2002) aesthetics metrics:

- **Edge crossings** (raw, normalized, per-edge)
- **Drawing area** (center-point bounding box)
- **Edge length coefficient of variation**

With a debug overlay (red dots at counted crossings, blue dashed bounding-box rectangle, green "unit edge" showing mean length, orange dashed std-dev line).

CSV export for paper-grade per-step snapshots.

### Statistics Modal (NEW)

New "📊 Statistics" button in the toolbar. Shows:
- Live (Cytoscape) vs Backend (/api/stats) totals side-by-side
- Per-type node/edge breakdowns
- Clean attack-graph metrics (excludes ATTACKER, COMPOUND, BRIDGE, CVE_GROUP, synthetic edges)
- Drawing quality metrics + debug overlay + CSV export
- Collapsible interpretation notes about common counting pitfalls

### skip_layer_2 Config (NEW)

Settings modal checkbox. When enabled:
- Only Layer 1 (external attack surface) is built
- INSIDE_NETWORK bridge node still present with ENTERS_NETWORK edges from L1 EX:Y
- Useful for measuring base graph complexity without lateral movement

### Initial State Box Fix

- Backend no longer creates `VC:UI:N` / `VC:AC:L`; they're managed by the frontend environment settings panel only
- Switching UI/AC settings properly replaces the node and re-compacts the box layout
- Duplicate VCs are gone

### CVE Merge + Compound Children Layout

After dagre runs, `compactCompoundChildren()` stacks compound children tightly around their centroid, preventing large merge groups and the Initial State box from spreading vertically.

### Smoother Zoom

Cytoscape `wheelSensitivity` lowered from default 1 to 0.3 for finer zoom control.

---

## API Reference

### Graph & Configuration

| Endpoint      | Method   | Description                  |
| ------------- | -------- | ---------------------------- |
| `/api/graph`  | GET      | Full graph as Cytoscape JSON |
| `/api/stats`  | GET      | Node/edge counts by type     |
| `/api/config` | GET/POST | Granularity configuration    |

### Data Upload & Rebuild (CHANGED in v2.0)

| Endpoint                                 | Method | Description                                   |
| ---------------------------------------- | ------ | --------------------------------------------- |
| `/api/upload/trivy`                      | POST   | Upload Trivy JSON file                        |
| `/api/data/rebuild`                      | POST   | **Returns `job_id`; worker runs on thread**   |
| `/api/data/rebuild/progress/{job_id}`    | GET    | **NEW: poll job status**                      |
| `/api/data/rebuild/cancel/{job_id}`      | POST   | **NEW: request cancellation**                 |
| `/api/data/scans`                        | GET    | List uploaded scans                           |
| `/api/data/reset`                        | POST   | Reset to mock data                            |

---

## Test Coverage

### Test Suites (~537 Total)

| Suite                      | Count   | Framework         |
| -------------------------- | ------- | ----------------- |
| `test_builder.py`          | ~84     | pytest            |
| `test_api_endpoints.py`    | ~30     | pytest            |
| `test_frontend.py`         | ~90     | pytest-playwright |
| `test_nvd_fetcher.py`      | ~24     | pytest            |
| `test_cwe_fetcher.py`      | ~48     | pytest            |
| `test_mongo_client.py`     | **16**  | pytest            |
| `test_jobs.py`             | **17**  | pytest            |
| `test_schema.py`           | ~20     | pytest            |
| TypeScript unit tests      | **156** | Vitest            |
| **Total**                  | **~537**|                   |

---

## Recent Changes (2026-04-11 → 2026-04-20)

### New Features

| Feature | Description |
|---------|-------------|
| **MongoDB persistence (3 phases)** | NVD/EPSS/CWE caches replaced with Mongo collections; docker-compose for Mongo; `init_mongo()` fail-fast |
| **Background rebuild jobs** | Rebuild returns job_id; polling endpoint exposes progress; 409 on concurrent |
| **Progress bar UI** | Phase label + percentage + N/total CVEs + current CVE + cancel button |
| **Drawing quality metrics** | Purchase (2002) — crossings (3 variants), drawing area, edge length CV; CSV export |
| **Debug overlay** | Red crossing dots, blue bounding box, green mean-edge, orange std-dev |
| **Statistics modal** | Dedicated wide-layout modal; Live vs Backend counts; per-type tables; clean metrics; interpretation notes |
| **skip_layer_2 config** | Build L1 only (keeps INSIDE_NETWORK bridge) |
| **Smoother zoom** | `wheelSensitivity: 0.3` with `minZoom`/`maxZoom` clamps |
| **Compact compound children** | Post-dagre layout step keeps Initial State and CVE_GROUP children tight |

### Bug Fixes

| Fix | Description |
|-----|-------------|
| **Initial State duplicate VCs** | Backend no longer emits UI/AC initial VCs; frontend env settings own them |
| **Env VC positioning** | New env VCs placed near existing ATTACKER_BOX siblings, then re-compacted |
| **GEXF export** | Strip dict/nested-list attributes before NetworkX export |
| **Circular import** | cveMerge ↔ filter resolved via injectGetHiddenTypes |
| **CVE merge cross-layer** | Merge keys include `layer` to prevent L1↔L2 grouping |

### New Files

| File | Description |
|------|-------------|
| `docker-compose.yml` | Mongo service + `pagdrawer_mongodb_data` volume |
| `Scripts/start-mongo.sh`, `kill-mongo.sh` | Mongo lifecycle |
| `src/data/mongo_client.py` | Singleton + TTL helpers |
| `src/data/jobs.py` | `JobManager` |
| `frontend/js/features/metrics.ts` | Drawing quality metrics + CSV |
| `frontend/js/features/rebuildProgress.ts` | Polling + progress bar |
| `frontend/js/ui/statistics.ts` | Stats modal |
| `Docs/Plans/MongoDB_Persistence.md` | 4-phase implementation plan |
| `Docs/initial_graph_metrics_guide.md` | ESORICS-paper metrics guide |

### New Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pymongo` | ≥4.6 | MongoDB driver (sync) |
| `mongomock` | ≥4.1 | In-memory Mongo for tests |

### Deferred / TODO

- **Phase D** of MongoDB persistence: global "Refresh all NVD data" button in Settings (per-rebuild force-refresh checkbox already exists)
- **STATIC_CWE_MAPPING** re-enablement after comparing live REST data against the in-code constant

---

## Known Limitations

1. **Mongo is required** — no offline/file-cache fallback
2. **First rebuild is slow** — NVD rate-limits at 6 s/CVE; 500 CVEs ≈ 50 min
3. **Cancel lag** — cancellation is checked between CVEs, so up to 6 s delay
4. **No persistence for graph config** — resets on backend restart
5. **Single-user** — no multi-user / auth
6. **Browser-only** — no desktop/mobile apps

---

## Research Foundation

> **Machalewski et al. (2024)** - "Expressing Impact of Vulnerabilities"
> Consensual Transformation Matrix from expert consensus on 22 CVEs,
> mapping 24 Technical Impact categories to Vector Changer privilege states.

Drawing quality metrics:

> **Purchase, H.C. (2002)** - "Metrics for Graph Drawing Aesthetics"
> Journal of Visual Languages and Computing, 13(5), 501–516.
