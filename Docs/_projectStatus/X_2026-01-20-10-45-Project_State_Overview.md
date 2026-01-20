# PAGDrawer - Project State Overview

**Date:** 2026-01-20  
**Version:** 1.4.0  
**Test Coverage:** ~380 tests across Python backend, TypeScript unit, and Playwright E2E

---

## Quick Start

```bash
# Backend (FastAPI on port 8000)
cd PAGDrawer
python -m uvicorn src.viz.app:app --reload --host 127.0.0.1 --port 8000

# Frontend (Vite dev server on port 3000)
cd frontend
npm run dev

# Run all tests
pytest tests/ -v                    # Python tests
npm run test                        # TypeScript unit tests
```

---

## What is PAGDrawer?

**PAGDrawer** (Privilege-based Attack Graph Drawer) transforms vulnerability scan data into interactive attack graphs. It models how attackers exploit vulnerabilities to escalate privileges and move laterally through networks.

Based on **Machalewski et al. (2024)** - "Expressing Impact of Vulnerabilities", implementing the **Consensual Transformation Matrix** for mapping technical impacts to privilege changes.

---

## Architecture Overview

### Tech Stack

| Layer    | Technology                       | Port |
| -------- | -------------------------------- | ---- |
| Backend  | Python 3.10 + FastAPI + NetworkX | 8000 |
| Frontend | TypeScript + Vite + Cytoscape.js | 3000 |
| Testing  | pytest + Playwright + Vitest     | -    |

### Directory Structure

```
PAGDrawer/
├── src/                        # Python backend
│   ├── core/                   # Config, schema, matrix
│   ├── data/loaders/           # Trivy, NVD, CWE fetchers
│   ├── graph/builder.py        # Graph construction
│   └── viz/app.py              # FastAPI REST API
├── frontend/                   # TypeScript frontend
│   ├── js/
│   │   ├── graph/              # Cytoscape core, layout, events
│   │   ├── features/           # Filter, visibility, exploitPaths
│   │   ├── ui/                 # Modal, tooltip, sidebar
│   │   └── services/api.ts     # Backend communication
│   └── css/styles.css
├── tests/                      # Test suites
│   ├── test_builder.py         # Graph builder tests
│   ├── test_api_endpoints.py   # API endpoint tests
│   └── test_frontend.py        # Playwright E2E tests
└── Docs/
    ├── _dailyNotes/            # Development logs (35+ entries)
    └── _projectStatus/         # Project snapshots (this file)
```

---

## Core Concept: The Attack Graph

### Node Types (8)

| Type         | Color   | Description         | Example                         |
| ------------ | ------- | ------------------- | ------------------------------- |
| **ATTACKER** | Magenta | Entry point         | Single starting node            |
| **HOST**     | Red     | Target machines     | `host-001` (web server)         |
| **CPE**      | Orange  | Software/products   | `cpe:2.3:a:apache:log4j:2.14.1` |
| **CVE**      | Yellow  | Vulnerabilities     | `CVE-2021-44228`                |
| **CWE**      | Green   | Weakness categories | `CWE-78`                        |
| **TI**       | Cyan    | Technical Impacts   | "Execute Unauthorized Code"     |
| **VC**       | Purple  | Vector Changers     | `AV:L`, `PR:H`, `EX:Y`          |
| **BRIDGE**   | Teal    | L1→L2 transition    | `INSIDE_NETWORK`                |

### Graph Flow

```
ATTACKER ─ENTERS_NETWORK→ HOST ─RUNS→ CPE ─HAS_VULN→ CVE ─IS_INSTANCE_OF→ CWE
                                                                          │
                                                                    HAS_IMPACT
                                                                          ↓
                         VC:EX:Y (terminal) ←LEADS_TO← TI ←───────────────┘
                              │
                         ENABLES (enables next attack phase)
                              ↓
                         VC → CVE (lateral movement)
```

### Edge Types (9)

| Edge             | Direction       | Description             |
| ---------------- | --------------- | ----------------------- |
| `ENTERS_NETWORK` | ATTACKER → HOST | Initial access          |
| `CAN_REACH`      | HOST → HOST     | Network connectivity    |
| `RUNS`           | HOST → CPE      | Software installation   |
| `HAS_VULN`       | CPE → CVE       | Vulnerability presence  |
| `IS_INSTANCE_OF` | CVE → CWE       | Weakness classification |
| `HAS_IMPACT`     | CWE → TI        | Impact from weakness    |
| `LEADS_TO`       | TI → VC         | Privilege state change  |
| `ENABLES`        | VC → CVE        | Multi-stage attacks     |
| `HAS_STATE`      | VC → ATTACKER   | Initial capabilities    |

---

## Key Features

### 1. Data Sources

| Source         | Description                     | Status     |
| -------------- | ------------------------------- | ---------- |
| Mock Data      | Built-in sample vulnerabilities | ✅ Default  |
| Trivy Upload   | JSON vulnerability scan results | ✅ Working  |
| NVD Enrichment | CVSS scores, descriptions       | ✅ Optional |
| CWE REST API   | Technical impact mappings       | ✅ Optional |

### 2. Granular Grouping (Singular/Universal Mode)

Nodes can be grouped at different levels via Settings modal sliders:

```
← More Universal (fewer nodes)          More Singular (more nodes) →
ATTACKER ────── HOST ────── CPE ────── CVE ────── CWE ────── TI
```

| Node | At ATTACKER Level        | At Most Granular                 |
| ---- | ------------------------ | -------------------------------- |
| CPE  | `cpe:nginx:1.0` (shared) | `cpe:nginx:1.0@host-001`         |
| CVE  | `CVE-2021-1234` (shared) | `CVE-2021-1234@cpe:...@host-001` |
| TI   | `TI:ExecCode` (shared)   | `TI:ExecCode@CWE-78@CVE-...`     |
| VC   | `VC:AV:N` (shared)       | `VC:AV:N@TI:...@CWE-...`         |

### 3. Two-Layer Attack Model

| Layer | Name         | Description                      |
| ----- | ------------ | -------------------------------- |
| L1    | External/DMZ | Directly reachable from ATTACKER |
| L2    | Internal     | Requires L1 compromise to reach  |

**INSIDE_NETWORK** bridge node connects layers.

### 4. Visibility Toggle System

Hide/show node types with eye icons:
- Hidden nodes removed from graph
- **Bridge edges** created to maintain connectivity
- **Bridge colors** now reflect hidden edge types (averaged, bright)
- Global edge storage ensures no edges lost on restore

### 5. Exploit Paths Filter

Highlights only paths leading to `EX:Y` (exploited) terminal nodes.

### 6. Dynamic Graph Stats

Settings modal shows **live** node/edge counts:
- Updates when visibility toggled
- Updates when Exploit Paths filtered
- Updates after singularity slider changes

### 7. Environment Filtering

Filter by CVSS environmental factors:
- **User Interaction (UI)**: None / Required
- **Attack Complexity (AC)**: Low / High

### 8. Reachability Filtering

Unreachable hosts visually dimmed (30% opacity, dotted border).

---

## API Reference

### Graph & Configuration

| Endpoint      | Method   | Description                  |
| ------------- | -------- | ---------------------------- |
| `/api/graph`  | GET      | Full graph as Cytoscape JSON |
| `/api/stats`  | GET      | Node/edge counts by type     |
| `/api/config` | GET/POST | Granularity configuration    |

### Data Upload

| Endpoint                 | Method | Description                 |
| ------------------------ | ------ | --------------------------- |
| `/api/upload/trivy`      | POST   | Upload Trivy JSON file      |
| `/api/upload/trivy/json` | POST   | Upload Trivy as JSON body   |
| `/api/data/scans`        | GET    | List uploaded scans         |
| `/api/data/scans/{id}`   | GET    | Get specific scan           |
| `/api/data/rebuild`      | POST   | Rebuild with scan selection |
| `/api/data/reset`        | POST   | Reset to mock data          |

### Swagger UI

Available at: `http://127.0.0.1:8000/docs`

---

## Test Coverage

### Test Suites

| Suite           | Count    | Framework         |
| --------------- | -------- | ----------------- |
| Python Backend  | ~75      | pytest            |
| TypeScript Unit | ~15      | Vitest            |
| Playwright E2E  | ~45      | pytest-playwright |
| **Total**       | **~135** |                   |

### Test Categories

| Category                | Description                       |
| ----------------------- | --------------------------------- |
| `test_builder.py`       | Graph construction, edge creation |
| `test_api_endpoints.py` | REST API endpoints                |
| `test_frontend.py`      | Browser interactions, visibility  |
| `filter.test.ts`        | TypeScript unit tests             |

---

## Recent Changes (2026-01-19 → 2026-01-20)

### Bug Fixes

| Fix                  | Description                                                     |
| -------------------- | --------------------------------------------------------------- |
| **VC Singularity**   | VCs now respect full context chain (HOST/CPE/CVE/CWE/TI levels) |
| **Edge Restoration** | Global edge storage prevents edge loss on visibility toggle     |
| **Scan Selection**   | Selector respects visibility state after rebuild                |

### New Features

| Feature                | Description                                                         |
| ---------------------- | ------------------------------------------------------------------- |
| **Bridge Edge Colors** | Dashed bridge edges colored by hidden edge types (averaged, bright) |
| **Dynamic Stats**      | Settings modal shows live node/edge counts                          |
| **Scan Selection**     | Multi-scan management with dropdown selector                        |

### UI Improvements

| Change             | Description                                             |
| ------------------ | ------------------------------------------------------- |
| **Sidebar Layout** | Data Source moved to top, stats moved to Settings modal |
| **Trivy Upload**   | Full upload workflow with scan list                     |

---

## Known Limitations

1. **No persistence** - Graph config resets on server restart
2. **Mock data only L1/L2** - No deeper network layers
3. **Browser-only** - No desktop or mobile apps
4. **Single user** - No multi-user support

---

## Future Enhancements (Backlog)

1. **Attack path scoring** - Risk-based path prioritization
2. **Export formats** - PNG, SVG, GraphML export
3. **Database persistence** - Save/load graphs
4. **Real-time scanning** - Direct Trivy integration
5. **Multi-layer networks** - Beyond L1/L2

---

## Research Foundation

> **Machalewski et al. (2024)** - "Expressing Impact of Vulnerabilities"
>
> Defines the Consensual Transformation Matrix derived from expert consensus
> on 22 CVEs, mapping 24 Technical Impact categories to Vector Changer
> privilege states (AV, PR, AC, S, CI, EX).

The matrix transforms vulnerability impacts into concrete privilege changes,
enabling attack path analysis and risk assessment.
