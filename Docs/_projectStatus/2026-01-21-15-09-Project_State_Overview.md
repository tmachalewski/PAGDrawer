# PAGDrawer - Project State Overview

**Date:** 2026-01-21  
**Version:** 1.5.0  
**Test Coverage:** 401 tests across Python backend, TypeScript unit, and Playwright E2E

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
pytest tests/ -v                    # Python tests (~300 tests)
npm run test                        # TypeScript unit tests (~15 tests)
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
│   ├── core/                   # Config, schema, consensual matrix
│   │   ├── config.py           # GraphConfig with granularity levels
│   │   ├── schema.py           # NodeType, EdgeType, VCType enums
│   │   └── consensual_matrix.py# TI → VC transformation matrix
│   ├── data/loaders/           # Data source integrations
│   │   ├── trivy_loader.py     # Trivy JSON parser
│   │   ├── nvd_fetcher.py      # NVD/EPSS enrichment
│   │   └── cwe_fetcher.py      # CWE technical impact fetcher
│   ├── graph/builder.py        # Graph construction (2-layer model)
│   └── viz/app.py              # FastAPI REST API
├── frontend/                   # TypeScript frontend
│   ├── js/
│   │   ├── config/             # Constants, slider config
│   │   ├── graph/              # Cytoscape core, layout, events
│   │   ├── features/           # Filter, visibility, search, exploitPaths
│   │   ├── ui/                 # Modal, tooltip, sidebar
│   │   └── services/api.ts     # Backend communication
│   └── css/styles.css          # All styling (800+ lines)
├── tests/                      # Test suites
│   ├── test_builder.py         # Graph builder tests (85 tests)
│   ├── test_api_endpoints.py   # API endpoint tests (30 tests)
│   ├── test_frontend.py        # Playwright E2E tests (90+ tests)
│   ├── test_nvd_fetcher.py     # NVD fetcher tests (25 tests)
│   ├── test_trivy_loader.py    # Trivy loader tests (30 tests)
│   └── test_schema.py          # Schema tests (20 tests)
└── Docs/
    ├── _dailyNotes/            # Development logs (40+ entries)
    ├── _projectStatus/         # Project snapshots (this file)
    └── _domains/               # Domain documentation
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
| `CAN_REACH`      | VC → HOST       | Network connectivity    |
| `RUNS`           | HOST → CPE      | Software installation   |
| `HAS_VULN`       | CPE → CVE       | Vulnerability presence  |
| `IS_INSTANCE_OF` | CVE → CWE       | Weakness classification |
| `HAS_IMPACT`     | CWE → TI        | Impact from weakness    |
| `LEADS_TO`       | TI → VC         | Privilege state change  |
| `ENABLES`        | VC → CVE        | Multi-stage attacks     |
| `HAS_STATE`      | VC → ATTACKER   | Initial capabilities    |

---

## Vector Changer (VC) State Machine

### VC Categories

| VC Type | Category      | Description                      |
| ------- | ------------- | -------------------------------- |
| **AV**  | State Mutator | Attack Vector (N, A, L, P)       |
| **PR**  | State Mutator | Privileges Required (N, L, H)    |
| **EX**  | State Mutator | Exploited (Y/N - terminal state) |
| **UI**  | Static Filter | User Interaction required (N, R) |
| **AC**  | Static Filter | Attack Complexity (L, H)         |

### VC Hierarchy (Attack Progression)

Gaining a VC unlocks CVEs requiring that level **or less permissive**:

**Attack Vector Hierarchy:**
```
Physical (P) > Local (L) > Adjacent (A) > Network (N)
   most           ←→              →→          least
```

| If you gain... | You can exploit CVEs requiring... |
| -------------- | --------------------------------- |
| `VC:AV:N`      | Only AV:N CVEs                    |
| `VC:AV:A`      | AV:N and AV:A CVEs                |
| `VC:AV:L`      | AV:N, AV:A, and AV:L CVEs         |
| `VC:AV:P`      | All attack vectors                |

**Privileges Required Hierarchy:**
```
High (H) > Low (L) > None (N)
```

| If you gain... | You can exploit CVEs requiring... |
| -------------- | --------------------------------- |
| `VC:PR:N`      | Only PR:N CVEs                    |
| `VC:PR:L`      | PR:N and PR:L CVEs                |
| `VC:PR:H`      | All privilege levels              |

---

## Key Features

### 1. Data Sources

| Source         | Description                     | Status     |
| -------------- | ------------------------------- | ---------- |
| Mock Data      | Built-in sample vulnerabilities | ✅ Default  |
| Trivy Upload   | JSON vulnerability scan results | ✅ Working  |
| NVD Enrichment | CVSS scores, descriptions       | ✅ Optional |
| CWE REST API   | Technical impact mappings       | ✅ Optional |

### 2. Granular Grouping (Universality Sliders)

Nodes can be grouped at different levels via Settings modal sliders:

```
← More Universal (ATTACKER)      More Granular (per-instance) →
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

Hide/show node types with eye icons (👁):
- Hidden nodes removed from graph
- **Bridge edges** created to maintain connectivity
- **Bridge colors** reflect hidden edge types (averaged, bright)
- Global edge storage ensures no edges lost on restore

### 5. Node Search Feature (NEW)

Real-time node search with:
- Case-insensitive partial matching
- 200ms debounce, 2+ character minimum
- Matching nodes highlighted, others dimmed
- Match count display
- Keyboard shortcuts: `/` or `Ctrl+F` to focus, `Escape` to clear
- `Enter` to fit view to matches

### 6. Exploit Paths Filter

Highlights only paths leading to `EX:Y` (exploited) terminal nodes.

### 7. Dynamic Graph Stats

Settings modal shows **live** node/edge counts:
- Updates when visibility toggled
- Updates when Exploit Paths filtered
- Updates after singularity slider changes

### 8. Environment Filtering (UI/AC)

Filter by CVSS environmental factors:
- **User Interaction (UI)**: None / Required
- **Attack Complexity (AC)**: Low / High

Unlike AV/PR VCs which are state changes, UI/AC are **static filters**:
- CVEs not meeting requirements are dimmed
- Cascade propagates to downstream CWE → TI → VC nodes

### 9. Reachability Filtering

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

### Test Suites (401 Total)

| Suite                   | Count   | Framework         |
| ----------------------- | ------- | ----------------- |
| `test_builder.py`       | ~85     | pytest            |
| `test_api_endpoints.py` | ~30     | pytest            |
| `test_frontend.py`      | ~90     | pytest-playwright |
| `test_nvd_fetcher.py`   | ~25     | pytest            |
| `test_trivy_loader.py`  | ~30     | pytest            |
| `test_schema.py`        | ~20     | pytest            |
| `conftest.py` fixtures  | -       | pytest            |
| TypeScript unit tests   | ~15     | Vitest            |
| **Total**               | **401** |                   |

### Test Categories

| Category                       | Description                                   |
| ------------------------------ | --------------------------------------------- |
| `TestDocumentedEdgeTypes`      | Verifies all edge types connect correct nodes |
| `TestVCHierarchyEnables`       | Verifies VC hierarchy enables correct CVEs    |
| `TestEnvironmentFilterCascade` | Verifies UI/AC filter cascades                |
| `TestNodeSearch`               | Node search functionality (12 tests)          |
| `TestVisibilityToggle`         | Bridge edges and restoration                  |
| `TestSettingsModal`            | Slider and config persistence                 |
| `TestScanSelection`            | Trivy upload and scan management              |

---

## Recent Changes (2026-01-20 → 2026-01-21)

### New Features

| Feature                     | Description                                               |
| --------------------------- | --------------------------------------------------------- |
| **Node Search**             | Real-time search with highlighting and keyboard shortcuts |
| **GraphNodeConnections.md** | Comprehensive domain documentation                        |

### Documentation

| Document                                | Description                              |
| --------------------------------------- | ---------------------------------------- |
| `Docs/_domains/GraphNodeConnections.md` | Node types, edges, VC hierarchy, sliders |

### New Tests (17 verification tests)

| Test Class                     | Count | Verifies                      |
| ------------------------------ | ----- | ----------------------------- |
| `TestDocumentedEdgeTypes`      | 8     | Edge type source/target nodes |
| `TestVCHierarchyEnables`       | 3     | VC ENABLES edge logic         |
| `TestEnvironmentFilterCascade` | 5     | UI/AC filter cascade          |
| `TestBridgeEdgeColor`          | 1     | Bridge edge color property    |
| `TestNodeSearch`               | 12    | Search functionality          |

---

## Frontend Module Overview

### `/frontend/js/features/`

| Module            | Purpose                                            |
| ----------------- | -------------------------------------------------- |
| `filter.ts`       | Node type visibility toggles, bridge edge creation |
| `environment.ts`  | UI/AC filtering, reachability dimming              |
| `exploitPaths.ts` | EX:Y terminal path highlighting                    |
| `search.ts`       | Node search with debounce and keyboard shortcuts   |

### `/frontend/js/graph/`

| Module      | Purpose                                |
| ----------- | -------------------------------------- |
| `core.ts`   | Cytoscape instance management, getCy() |
| `layout.ts` | Dagre layout configuration             |
| `events.ts` | Click, hover, select event handlers    |
| `styles.ts` | Cytoscape style definitions            |

### `/frontend/js/ui/`

| Module       | Purpose                          |
| ------------ | -------------------------------- |
| `modal.ts`   | Settings modal, slider handling  |
| `tooltip.ts` | Node details tooltip (draggable) |
| `sidebar.ts` | Data source panel, scan selector |

---

## Backend Module Overview

### `/src/core/`

| Module                 | Purpose                                 |
| ---------------------- | --------------------------------------- |
| `config.py`            | GraphConfig with granularity levels     |
| `schema.py`            | NodeType, EdgeType, VCType, dataclasses |
| `consensual_matrix.py` | TI → VC transformation mapping          |

### `/src/graph/`

| Module       | Purpose                                         |
| ------------ | ----------------------------------------------- |
| `builder.py` | KnowledgeGraphBuilder, 2-layer model, VC wiring |

### `/src/data/loaders/`

| Module            | Purpose                           |
| ----------------- | --------------------------------- |
| `trivy_loader.py` | Parse Trivy JSON scan results     |
| `nvd_fetcher.py`  | Fetch CVE details and EPSS scores |
| `cwe_fetcher.py`  | Fetch CWE technical impacts       |

### `/src/viz/`

| Module   | Purpose                                     |
| -------- | ------------------------------------------- |
| `app.py` | FastAPI routes, graph/config/scan endpoints |

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
6. **VC hierarchy visualization** - Show enabled paths from gained VCs

---

## Configuration Reference

### GraphConfig Granularity Levels

```python
GROUPING_HIERARCHY = ["ATTACKER", "HOST", "CPE", "CVE", "CWE", "TI", "VC"]

# Default configuration
{
    "HOST": "ATTACKER",  # Hosts are always anchors
    "CPE": "HOST",       # CPE per host
    "CVE": "CPE",        # CVE per CPE
    "CWE": "CVE",        # CWE per CVE
    "TI": "CWE",         # TI per CWE
    "VC": "TI",          # VC per TI (most granular)
}
```

### Valid Grouping Levels

| Node | Valid Positions                   |
| ---- | --------------------------------- |
| CPE  | ATTACKER, HOST                    |
| CVE  | ATTACKER, HOST, CPE               |
| CWE  | ATTACKER, HOST, CPE, CVE          |
| TI   | ATTACKER, HOST, CPE, CVE, CWE     |
| VC   | ATTACKER, HOST, CPE, CVE, CWE, TI |

---

## Research Foundation

> **Machalewski et al. (2024)** - "Expressing Impact of Vulnerabilities"
>
> Defines the Consensual Transformation Matrix derived from expert consensus
> on 22 CVEs, mapping 24 Technical Impact categories to Vector Changer
> privilege states (AV, PR, AC, S, CI, EX).

The matrix transforms vulnerability impacts into concrete privilege changes,
enabling attack path analysis and risk assessment.

---

## Git History (Recent Commits)

```
aecdf43 docs: Add GraphNodeConnections.md explaining graph structure
e6a9bf7 test: Add verification tests for GraphNodeConnections.md documentation
b605e25 feat: Add search UI and integration
c6b971c feat: Add node search feature with E2E tests
f8dda12 docs: Update daily note with test fixes and regression test details
```
