# PAGDrawer - Project State Overview

**Date:** 2026-04-11
**Version:** 1.8.0
**Test Coverage:** ~330 Python tests + 118 TypeScript unit tests = ~448 total

---

## Quick Start

```bash
# Backend (FastAPI on port 8000)
bash Scripts/start-backend.sh

# Frontend (Vite dev server on port 3000)
bash Scripts/start-frontend.sh

# Stop servers
bash Scripts/kill-backend.sh
bash Scripts/kill-frontend.sh

# Run all tests
pytest tests/ -v                    # Python tests (~330 tests)
cd frontend && npm run test         # TypeScript unit tests (118 tests)
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
│   │   ├── features/           # Filter, visibility, search, exploitPaths, exportSvg, theme, cveMerge
│   │   ├── ui/                 # Modal, tooltip, sidebar
│   │   └── services/api.ts     # Backend communication
│   └── css/styles.css          # All styling (1060+ lines, includes light theme)
├── examples/                   # Example data files
│   ├── sample_trivy_scan.json  # Multi-target scan (nginx, python, postgres)
│   └── slider_showcase_trivy_scan.json  # Single-host scan for slider demos
├── tests/                      # Test suites
│   ├── test_builder.py         # Graph builder tests (~76 tests)
│   ├── test_api_endpoints.py   # API endpoint tests (~25 tests)
│   ├── test_frontend.py        # Playwright E2E tests (~90 tests)
│   ├── test_nvd_fetcher.py     # NVD fetcher tests (~25 tests)
│   ├── test_trivy_loader.py    # Trivy loader tests (~30 tests)
│   └── test_schema.py          # Schema tests (~20 tests)
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

### Node Types (9)

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
| **CVE_GROUP**| Yellow  | Merged CVE compound | `AV:N / AC:L / PR:N / UI:N (×5)` |

### Graph Flow (Chain-Depth Aware)

```
ATTACKER -CAN_REACH-> HOST -RUNS-> CPE -HAS_VULN-> CVE:d0 -IS_INSTANCE_OF-> CWE:d0
                                                                                |
                                                                          HAS_IMPACT
                                                                                v
                         VC:EX:Y:d0 (terminal) <-LEADS_TO- TI:d0 <------------+
                         VC:AV:L:d0             <-LEADS_TO-+
                         VC:PR:H:d0             <-LEADS_TO-+
                              |                      |
                         ENABLES (depth 0 → depth 1)
                              v
                         CVE:d1 → CWE:d1 → TI:d1 → VC:d1 (next attack stage)
```

Nodes carry `:dN` depth suffix. ENABLES edges only go forward (depth N → N+1).

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

### 3. Two-Layer Attack Model

| Layer | Name         | Description                      |
| ----- | ------------ | -------------------------------- |
| L1    | External/DMZ | Directly reachable from ATTACKER |
| L2    | Internal     | Requires L1 compromise to reach  |

### 4. Visibility Toggle System

Hide/show node types with eye icons. Bridge edges maintain connectivity when intermediate types are hidden.

### 5. CVE Merge Modes

When CWE+TI are hidden, merge CVE nodes into compound boxes:
- **By Prerequisites**: Groups CVEs with identical AV/AC/PR/UI requirements
- **By Outcomes**: Groups CVEs producing same VC states; consolidates edges from compound parent
- Layer-aware and depth-aware to prevent cross-layer/cross-stage grouping
- Children remain hoverable inside compound for tooltip inspection

### 6. Node Search Feature

Real-time node search with case-insensitive partial matching, 200ms debounce, keyboard shortcuts.

### 7. Exploit Paths Filter

Highlights only paths leading to `EX:Y` (exploited) terminal nodes.

### 8. Environment Filtering (UI/AC)

Filter by CVSS environmental factors with cascade propagation.

### 9. SVG Export

Export selected graph elements as SVG for academic papers.

### 10. Light Theme

Toggle between dark and light themes for print-ready images.

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

---

## Test Coverage

### Test Suites (~448 Total)

| Suite                   | Count   | Framework         |
| ----------------------- | ------- | ----------------- |
| `test_builder.py`       | ~76     | pytest            |
| `test_api_endpoints.py` | ~25     | pytest            |
| `test_frontend.py`      | ~90     | pytest-playwright |
| `test_nvd_fetcher.py`   | ~25     | pytest            |
| `test_trivy_loader.py`  | ~30     | pytest            |
| `test_schema.py`        | ~20     | pytest            |
| TypeScript unit tests   | 118     | Vitest            |
| **Total**               | **~448**|                   |

### Notable Test Classes

| Category                           | Description                                   |
| ---------------------------------- | --------------------------------------------- |
| `TestDocumentedEdgeTypes`          | Verifies all edge types connect correct nodes |
| `TestVCHierarchyEnables`          | Verifies VC hierarchy enables correct CVEs    |
| `TestVCGranularityEnablesEdges`   | Verifies ENABLES edges at all VC granularities |
| `TestCVEMergeAttributes`          | Verifies prereqs and vc_outcomes on CVE nodes |
| `TestEnvironmentFilterCascade`     | Verifies UI/AC filter cascades                |
| `cveMerge.test.ts`                | 36 tests for merge key computation, grouping, edge consolidation |

---

## Recent Changes (2026-04-10 -> 2026-04-11)

### New Features

| Feature | Description |
|---------|-------------|
| **CVE Merge Modes** | Group CVEs by prereqs or outcomes using Cytoscape compound nodes |
| **Edge consolidation** | Outcomes mode hides individual edges, creates deduped synthetic edges from compound |
| **Merge button UX** | Always-visible button, disabled with tooltip hint when CWE/TI not hidden |
| **Toast notification** | One-time notification when merge first becomes available |
| **prereqs attribute** | CVE nodes carry parsed CVSS prerequisites dict |
| **vc_outcomes attribute** | CVE nodes carry sorted list of VC outcomes from CWE→TI→VC chain |

### Bug Fixes

| Fix | Description |
|-----|-------------|
| **GEXF export** | Strip non-serializable attributes (dict, nested list) before GEXF export |
| **Circular import** | Resolved cveMerge↔filter circular dependency via injection pattern |
| **Cross-layer merging** | Added layer (L1/L2) to merge key to prevent grouping across attack layers |

### New Files

| File | Description |
|------|-------------|
| `frontend/js/features/cveMerge.ts` | CVE merge logic module (~310 lines) |
| `frontend/js/features/cveMerge.test.ts` | 36 unit tests for merge feature |
| `Docs/_domains/CVEMergeModes.md` | Domain documentation for merge feature |
| `Docs/Plans/CVE_Merge_Modes.md` | Implementation plan |

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

---

## Known Limitations

1. **No persistence** - Graph config resets on server restart
2. **Mock data only L1/L2** - No deeper network layers
3. **Browser-only** - No desktop or mobile apps
4. **Single user** - No multi-user support
5. **Compound sizing** - Large merge groups (10+ CVEs) can produce tall compound boxes due to dagre layout

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
b3e42ba fix: Visibility toggle loses edges when re-showing node types
2e99552 Merge branch 'feature/chain-depth-aware-attacks' into master
fb125af feat: Chain-depth-aware multi-stage attack wiring via BFS
6a4bb89 docs: Add daily note for multi-CWE/attack chains and update project status
0d99263 feat: Multi-CWE support, multi-stage attacks, node counts, and tooltip fix
d99231d docs: Add daily note for SVG export and light theme, update project status
2e1a8a4 feat: Add light theme toggle for print-friendly graph exports
46b64ee feat: Add SVG export for selected graph elements
```
