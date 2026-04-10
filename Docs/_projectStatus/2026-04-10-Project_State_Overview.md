# PAGDrawer - Project State Overview

**Date:** 2026-04-10
**Version:** 1.6.0
**Test Coverage:** 406 Python tests + 82 TypeScript unit tests = 488 total

---

## Quick Start

```bash
# Backend (FastAPI on port 8000)
cd PAGDrawer
source venv/Scripts/activate
python -m uvicorn src.viz.app:app --reload --host 127.0.0.1 --port 8000

# Frontend (Vite dev server on port 3000)
cd frontend
npm run dev

# Run all tests
pytest tests/ -v                    # Python tests (406 tests)
npm run test                        # TypeScript unit tests (82 tests)
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
│   │   └── consensual_matrix.py# TI -> VC transformation matrix
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
│   │   ├── features/           # Filter, visibility, search, exploitPaths, exportSvg, theme
│   │   ├── ui/                 # Modal, tooltip, sidebar
│   │   └── services/api.ts     # Backend communication
│   └── css/styles.css          # All styling (990+ lines, includes light theme)
├── examples/                   # Example data files
│   ├── sample_trivy_scan.json  # Multi-target scan (nginx, python, postgres)
│   └── slider_showcase_trivy_scan.json  # Single-host scan for slider demos
├── tests/                      # Test suites
│   ├── test_builder.py         # Graph builder tests (70 tests)
│   ├── test_api_endpoints.py   # API endpoint tests (25 tests)
│   ├── test_frontend.py        # Playwright E2E tests (90+ tests)
│   ├── test_nvd_fetcher.py     # NVD fetcher tests (25 tests)
│   ├── test_trivy_loader.py    # Trivy loader tests (30 tests)
│   └── test_schema.py          # Schema tests (20 tests)
├── Scripts/                    # Utility scripts
│   ├── start-backend.sh        # Start backend with venv
│   ├── start-frontend.sh       # Start frontend dev server
│   ├── kill-backend.sh         # Stop backend
│   ├── kill-frontend.sh        # Stop frontend
│   └── trivyscangeneration.txt # Docker command for real Trivy scans
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
| **BRIDGE**   | Teal    | L1->L2 transition   | `INSIDE_NETWORK`                |

### Graph Flow

```
ATTACKER -ENTERS_NETWORK-> HOST -RUNS-> CPE -HAS_VULN-> CVE -IS_INSTANCE_OF-> CWE
                                                                          |
                                                                    HAS_IMPACT
                                                                          v
                         VC:EX:Y (terminal) <-LEADS_TO- TI <-------------+
                              |
                         ENABLES (enables next attack phase)
                              v
                         VC -> CVE (lateral movement)
```

### Edge Types (9)

| Edge             | Direction       | Description             |
| ---------------- | --------------- | ----------------------- |
| `ENTERS_NETWORK` | ATTACKER -> HOST | Initial access          |
| `CAN_REACH`      | VC -> HOST       | Network connectivity    |
| `RUNS`           | HOST -> CPE      | Software installation   |
| `HAS_VULN`       | CPE -> CVE       | Vulnerability presence  |
| `IS_INSTANCE_OF` | CVE -> CWE       | Weakness classification |
| `HAS_IMPACT`     | CWE -> TI        | Impact from weakness    |
| `LEADS_TO`       | TI -> VC         | Privilege state change  |
| `ENABLES`        | VC -> CVE        | Multi-stage attacks     |
| `HAS_STATE`      | VC -> ATTACKER   | Initial capabilities    |

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
   most           <->              ->          least
```

**Privileges Required Hierarchy:**
```
High (H) > Low (L) > None (N)
```

---

## Key Features

### 1. Data Sources

| Source         | Description                     | Status     |
| -------------- | ------------------------------- | ---------- |
| Mock Data      | Built-in sample vulnerabilities | Default    |
| Trivy Upload   | JSON vulnerability scan results | Working    |
| NVD Enrichment | CVSS scores, descriptions       | Optional   |
| CWE REST API   | Technical impact mappings       | Optional   |

### 2. Granular Grouping (Universality Sliders)

Nodes can be grouped at different levels via Settings modal sliders:

```
<- More Universal (ATTACKER)      More Granular (per-instance) ->
ATTACKER ------ HOST ------ CPE ------ CVE ------ CWE ------ TI
```

**Enrichment caching**: When sliders change, cached enriched data is reused so TI/VC nodes are preserved without re-fetching from external APIs.

**Config reset**: Loading a new scan resets all sliders to defaults.

### 3. Two-Layer Attack Model

| Layer | Name         | Description                      |
| ----- | ------------ | -------------------------------- |
| L1    | External/DMZ | Directly reachable from ATTACKER |
| L2    | Internal     | Requires L1 compromise to reach  |

### 4. Visibility Toggle System

Hide/show node types with eye icons:
- Hidden nodes removed from graph
- **Bridge edges** created to maintain connectivity
- Global edge storage ensures no edges lost on restore

### 5. Node Search Feature

Real-time node search with:
- Case-insensitive partial matching
- 200ms debounce, 2+ character minimum
- Keyboard shortcuts: `/` or `Ctrl+F` to focus, `Escape` to clear, `Enter` to fit

### 6. Exploit Paths Filter

Highlights only paths leading to `EX:Y` (exploited) terminal nodes.

### 7. Environment Filtering (UI/AC)

Filter by CVSS environmental factors:
- **User Interaction (UI)**: None / Required
- **Attack Complexity (AC)**: Low / High
- Cascade propagation dims CWE -> TI -> VC nodes downstream

### 8. Dynamic Graph Stats

Settings modal shows **live** node/edge counts that update on all changes.

### 9. SVG Export

Export selected graph elements as SVG for academic papers:
- Select nodes, click "Export SVG" — exports selection and connecting edges
- If nothing selected, exports entire visible graph
- Uses `cytoscape-svg` extension with 2x scale
- SVG background adapts to active theme (dark/light)

### 10. Light Theme

Toggle between dark and light themes via toolbar button:
- Light theme: white background, high-contrast node colors, dark text
- Designed for print-ready images in academic papers
- Both UI and Cytoscape graph styles update simultaneously

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

### Test Suites (488 Total)

| Suite                   | Count   | Framework         |
| ----------------------- | ------- | ----------------- |
| `test_builder.py`       | ~70     | pytest            |
| `test_api_endpoints.py` | ~25     | pytest            |
| `test_frontend.py`      | ~90     | pytest-playwright |
| `test_nvd_fetcher.py`   | ~25     | pytest            |
| `test_trivy_loader.py`  | ~30     | pytest            |
| `test_schema.py`        | ~20     | pytest            |
| `conftest.py` fixtures  | -       | pytest            |
| TypeScript unit tests   | ~82     | Vitest            |
| **Total**               | **488** |                   |

### Notable Test Classes

| Category                           | Description                                   |
| ---------------------------------- | --------------------------------------------- |
| `TestDocumentedEdgeTypes`          | Verifies all edge types connect correct nodes |
| `TestVCHierarchyEnables`          | Verifies VC hierarchy enables correct CVEs    |
| `TestVCGranularityEnablesEdges`   | Verifies ENABLES edges at all VC granularities |
| `TestEnvironmentFilterCascade`     | Verifies UI/AC filter cascades                |
| `TestNodeSearch`                   | Node search functionality (12 tests)          |
| `TestVisibilityToggle`             | Bridge edges and restoration                  |
| `TestSettingsModal`                | Slider and config persistence                 |

---

## Recent Changes (2026-01-21 -> 2026-04-10)

### Bug Fixes

| Fix | Description |
|-----|-------------|
| **Enrichment cache** | Config changes no longer discard TI/VC enrichment data |
| **ENABLES edge lookup** | Universal VC nodes correctly matched in multistage attack wiring |
| **Slider reset** | New scan loads reset slider config to defaults |
| **Multi-CWE per CVE** | All CWEs now processed per CVE, not just the first one |
| **ENABLES edge dict collision** | VC nodes with same (type,value,host) but different context no longer overwritten |
| **Attacker connectivity** | Default subnet_id changed to "dmz" for proper CAN_REACH edges |
| **Tooltip after rebuild** | Tooltips now re-initialize after Trivy upload/graph rebuild |

### New Features

| Feature | Description |
|---------|-------------|
| **SVG Export** | Export selected nodes/edges as SVG via `cytoscape-svg` extension |
| **Light Theme** | Dark/light toggle for print-friendly graph images |
| **Multi-CWE support** | CVEs can map to multiple CWEs with per-CWE TI/VC chains |
| **Initial attacker VCs** | Attacker starts with AV:N, PR:N, UI:N, AC:L capabilities |
| **Per-type node counts** | Live node counts next to sliders in settings modal |
| **Multi-stage attacks** | AV:L CVE (CVE-2022-2588) demonstrates chained exploitation |

### New Files

| File | Description |
|------|-------------|
| `frontend/js/features/exportSvg.ts` | SVG export logic with selection support |
| `frontend/js/features/theme.ts` | Theme toggle with light-mode color maps |
| `examples/slider_showcase_trivy_scan.json` | Single-host scan with 7 CVEs for slider/attack demos |
| `Scripts/trivyscangeneration.txt` | Docker command for generating real Trivy scans |
| `.claude/launch.json` | Dev server configurations for backend and frontend |

### New Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `cytoscape-svg` | 0.4.0 | SVG rendering from Cytoscape canvas |

### New Tests

| Test Class | Count | Verifies |
|------------|-------|----------|
| `TestVCGranularityEnablesEdges` | 5 | ENABLES edges at all VC granularity levels |

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

## Known Limitations

1. **No persistence** - Graph config resets on server restart
2. **Mock data only L1/L2** - No deeper network layers
3. **Browser-only** - No desktop or mobile apps
4. **Single user** - No multi-user support

---

## Research Foundation

> **Machalewski et al. (2024)** - "Expressing Impact of Vulnerabilities"
>
> Defines the Consensual Transformation Matrix derived from expert consensus
> on 22 CVEs, mapping 24 Technical Impact categories to Vector Changer
> privilege states (AV, PR, AC, S, CI, EX).

---

## Git History (Recent Commits)

```
0d99263 feat: Multi-CWE support, multi-stage attacks, node counts, and tooltip fix
d99231d docs: Add daily note for SVG export and light theme, update project status
2e1a8a4 feat: Add light theme toggle for print-friendly graph exports
46b64ee feat: Add SVG export for selected graph elements
aa9946e docs: Add Trivy scan generation command reference
bb5b488 fix: Preserve enrichment data when changing granularity sliders and reset config on rebuild
6d59f37 chore: Clean up requirements.txt and update start script for venv
d4aef42 chore: Add Docs HTML files to gitignore
958f735 docs: Add daily note and project status for 2026-01-21
```
