# PAGDrawer - Project State Overview
**Date:** 2026-01-11 22:38

## Project Summary
**PAGDrawer** (Predictive Attack Graph Drawer) is a visualization tool for security attack graphs. It models how vulnerabilities on a network can be exploited to gain privileges and move laterally through systems.

## Architecture

### Backend (Python/FastAPI)
- **Framework**: FastAPI + Uvicorn
- **Graph Library**: NetworkX
- **Entry Point**: `src/viz/app.py`

### Frontend (Modular ES6 JavaScript)
- **Visualization**: Cytoscape.js with Dagre layout
- **Entry Point**: `frontend/index.html` (imports `js/main.js`)
- **CSS**: `frontend/css/styles.css`

## Frontend File Structure (Refactored)
```
frontend/
├── index.html              # Minimal HTML + module imports
├── css/
│   └── styles.css          # Extracted CSS (315 lines)
└── js/
    ├── main.js             # Entry point, initializes app
    ├── config/
    │   └── constants.js    # Colors, Cytoscape styles
    ├── services/
    │   └── api.js          # API calls (fetchGraph, fetchStats)
    ├── graph/
    │   ├── core.js         # Cytoscape initialization
    │   ├── layout.js       # Layout algorithms
    │   └── events.js       # Event handlers
    ├── features/
    │   ├── filter.js       # Node type filtering
    │   ├── environment.js  # UI/AC filtering + reachability
    │   ├── hideRestore.js  # Hide/restore nodes
    │   └── exploitPaths.js # Exploit path highlighting
    └── ui/
        ├── sidebar.js      # Stats, loading states
        └── modal.js        # Settings modal
```

## Node Schema (6 Types)
| Type | Color  | Description                                    |
| ---- | ------ | ---------------------------------------------- |
| HOST | Red    | Infrastructure targets (servers)               |
| CPE  | Orange | Software/products installed on hosts           |
| CVE  | Yellow | Vulnerabilities in software                    |
| CWE  | Green  | Weakness categories                            |
| TI   | Cyan   | Technical Impacts (what exploitation achieves) |
| VC   | Purple | Vector Changers (attacker capabilities)        |

## Graph Flow
```
ATTACKER → HOST → CPE → CVE → CWE → TI → VC
                                         ↓
                                    (ENABLES next attack)
```

**Edge Types:**
- `CAN_REACH` - Attacker to HOST
- `RUNS` - HOST to CPE
- `HAS_VULN` - CPE to CVE
- `IS_INSTANCE_OF` - CVE to CWE
- `HAS_IMPACT` - CWE to TI
- `LEADS_TO` - TI to VC
- `ENABLES` - VC enables further exploitation
- `HAS_STATE` - Initial VCs to ATTACKER

## Key Features

### Reachability Filtering (NEW)
- Hosts without `CAN_REACH` edge from ATTACKER are dimmed (30% opacity)
- Downstream nodes (CPE, CVE, CWE, TI, VC) of unreachable hosts also dimmed
- Reachable: `host-001`, `host-002` | Unreachable: `host-003` to `host-006`
- Filter interactions preserve unreachable styling

### Environment Filtering
- **UI Setting**: None (UI:N) or Required (UI:R)
- **AC Setting**: Low (AC:L) or High (AC:H)
- Filters CVEs based on CVSS requirements
- **Cascade filtering**: Filtered CVEs → CWE → TI → VC also dimmed

### Attacker Initial State
- Compound node "ATTACKER_BOX" contains:
  - Hacker node
  - Initial VCs: AV:N, PR:N
  - Environment VCs: UI, AC (dynamic)
- VCs point TO attacker (showing initial capabilities)

### Interactive Features
- **Exploit Paths**: Highlights paths from ATTACKER to EXPLOITED (EX:Y) terminals
- **Hide/Restore**: H key hides selected nodes, creates bridge edges
- **Filter by Type**: Filter visibility by node type
- **Node Details**: Click to view full node data
- **Layouts**: Dagre (DAG), Breadthfirst, Force-directed, Circle

## Current Statistics
- **Total Nodes**: 175
- **Total Edges**: 218
- **Frontend Tests**: 33 (all passing)

## Testing
```bash
# Run all frontend tests
pytest tests/test_frontend.py -v --base-url=http://localhost:8000

# Run specific test class
pytest tests/test_frontend.py::TestReachabilityFiltering -v --base-url=http://localhost:8000
```

## Running the Application
```bash
cd PAGDrawer
uvicorn src.viz.app:app --reload --host 0.0.0.0 --port 8000
# Open http://localhost:8000
```

## Recent Changes (2026-01-11)
- **Frontend Refactoring**: Split monolithic `index.html` into ES6 modules
- **Reachability Filtering**: Dim unreachable hosts and downstream nodes
- **Filter Preservation**: Unreachable styling preserved during type filtering
- **Tests**: Added 6 reachability tests (total 33 frontend tests)
- **Exposed `window.cy`**: For Playwright test access
