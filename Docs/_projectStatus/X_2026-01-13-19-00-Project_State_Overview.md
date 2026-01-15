# PAGDrawer - Project State Overview
**Date:** 2026-01-13 19:00

## Project Summary
**PAGDrawer** (Predictive Attack Graph Drawer) is a visualization tool for security attack graphs. It models how vulnerabilities across a network can be exploited to gain privileges and pivot laterally through systems.

---

## Architecture

### Backend (Python/FastAPI)
| Component     | Technology        |
| ------------- | ----------------- |
| Framework     | FastAPI + Uvicorn |
| Graph Library | NetworkX          |
| Entry Point   | `src/viz/app.py`  |
| Port          | 8000              |

### Frontend (TypeScript/Vite)
| Component     | Technology                  |
| ------------- | --------------------------- |
| Build Tool    | Vite                        |
| Visualization | Cytoscape.js + Dagre layout |
| Language      | TypeScript (strict mode)    |
| Port          | 3000 (dev server)           |

---

## Node Schema (7 Types)

| Type     | Color  | Description                               |
| -------- | ------ | ----------------------------------------- |
| HOST     | Red    | Infrastructure targets (servers)          |
| CPE      | Orange | Software/products installed on hosts      |
| CVE      | Yellow | Vulnerabilities in software               |
| CWE      | Green  | Weakness categories                       |
| TI       | Cyan   | Technical Impacts (exploitation outcomes) |
| VC       | Purple | Vector Changers (attacker capabilities)   |
| ATTACKER | Gold   | Threat actor starting point               |

## Graph Flow
```
ATTACKER → HOST → CPE → CVE → CWE → TI → VC
                                          ↓
                                    (ENABLES next attack)
```

**Edge Types:**
| Edge           | Direction       | Description             |
| -------------- | --------------- | ----------------------- |
| CAN_REACH      | ATTACKER → HOST | Network accessibility   |
| RUNS           | HOST → CPE      | Software installation   |
| HAS_VULN       | CPE → CVE       | Vulnerability presence  |
| IS_INSTANCE_OF | CVE → CWE       | Weakness classification |
| HAS_IMPACT     | CWE → TI        | Impact from weakness    |
| LEADS_TO       | TI → VC         | Capability gained       |
| ENABLES        | VC → CVE        | Multi-stage attack      |
| HAS_STATE      | VC → ATTACKER   | Initial capabilities    |
| PIVOTS_TO      | VC → HOST       | Lateral movement        |

---

## Two-Layer Model

| Layer | Name         | Description                      |
| ----- | ------------ | -------------------------------- |
| L1    | DMZ/External | Directly reachable from attacker |
| L2    | Internal     | Accessible only after pivoting   |

**Bridge Node:** `INSIDE_NETWORK` connects L1 to L2

---

## Key Features

### 1. Environment Filtering
- **UI Setting**: None (UI:N) or Required (UI:R)
- **AC Setting**: Low (AC:L) or High (AC:H)
- Cascade filtering: CVE → CWE → TI → VC

### 2. Reachability Filtering
- **Reachable hosts** (via CAN_REACH): Full opacity
- **Unreachable L1 hosts**: Dimmed (30% opacity, gray dotted border)
- **Selected unreachable**: Lighter (60% opacity, white border)
- **L2 hosts**: Always reachable via jump hosts
- **Algorithm**: Forward BFS from ATTACKER to collect reachable set

### 3. Node Grouping (Singular/Universal)
| Node Type | Default  | Singular ID                | Universal ID |
| --------- | -------- | -------------------------- | ------------ |
| CPE       | singular | `cpe:...@host-001`         | `cpe:...`    |
| CVE       | singular | `CVE-...@cpe:...@host-001` | `CVE-...`    |
| CWE       | singular | `CWE-...@CVE-...@...`      | `CWE-...`    |
| TI        | singular | `TI:impact@CWE-...@...`    | `TI:impact`  |
| VC        | singular | `VC:AV:N@host-001`         | `VC:AV:N`    |

### 4. Interactive Features
- **Multi-Select Tooltips**: Hover/click to see node details with arrows
- **CTRL+Click**: Multi-select nodes
- **Draggable Tooltips**: Reposition tooltip windows
- **SVG Arrows**: Dashed lines from tooltips to nodes
- **Exploit Paths**: Highlight paths to EX:Y terminals
- **Hide/Restore**: H key hides, creates bridge edges
- **Filter by Type**: Sidebar filter buttons
- **Layouts**: Dagre, Breadthfirst, Force-directed, Circle

---

## File Structure

```
PAGDrawer/
├── frontend/
│   ├── index.html              # Main HTML
│   ├── vite.config.ts          # Vite + Vitest config
│   ├── tsconfig.json           # TypeScript strict config
│   ├── css/
│   │   └── styles.css          # Extracted CSS
│   └── js/
│       ├── main.ts             # Entry point
│       ├── types.ts            # TypeScript definitions
│       ├── config/constants.ts # Colors, Cytoscape styles
│       ├── services/api.ts     # Backend communication
│       ├── graph/{core,layout,events}.ts
│       ├── features/{filter,environment,hideRestore,exploitPaths}.ts
│       └── ui/{sidebar,modal,tooltip}.ts
├── src/
│   ├── core/
│   │   ├── schema.py           # NodeType, EdgeType enums
│   │   ├── config.py           # Graph configuration
│   │   └── consensual_matrix.py
│   ├── data/mock_data.py       # Sample data
│   ├── graph/builder.py        # KnowledgeGraphBuilder
│   └── viz/app.py              # FastAPI application
├── tests/
│   ├── test_builder.py         # 46 tests
│   ├── test_api.py             # 14 tests
│   ├── test_config.py          # Config tests
│   ├── test_schema.py          # Schema tests
│   └── test_frontend.py        # 37 Playwright tests
└── Docs/
    ├── _dailyNotes/            # Development logs
    ├── _projectStatus/         # Project snapshots
    └── _PythonTestingStandards.md
```

---

## Test Coverage

### Python Backend
| Module                          | Coverage |
| ------------------------------- | -------- |
| `src/core/config.py`            | 100%     |
| `src/core/consensual_matrix.py` | 97%      |
| `src/core/schema.py`            | 91%      |
| `src/graph/builder.py`          | 93%      |
| `src/viz/app.py`                | 95%      |
| **TOTAL**                       | **94%**  |

### Test Suites
| Suite              | Tests   | Framework         |
| ------------------ | ------- | ----------------- |
| Python Backend     | 66      | pytest            |
| TypeScript Unit    | 9       | Vitest            |
| Playwright Browser | 37      | pytest-playwright |
| **TOTAL**          | **112** |                   |

---

## Running the Application

```bash
# Backend
cd PAGDrawer
uvicorn src.viz.app:app --reload --host 0.0.0.0 --port 8000

# Frontend (dev)
cd frontend
npm run dev

# Tests
pytest tests/ -v                            # All Python tests
npm run test                                # TypeScript unit tests
$env:PYTEST_BASE_URL='http://localhost:3000'; pytest tests/test_frontend.py  # Browser tests
```

---

## Recent Changes (2026-01-13)

### Multi-Select Draggable Tooltips (NEW)
- Moved Node Details from sidebar to hover tooltips
- CTRL+Click multi-select support
- Draggable tooltip windows
- SVG dashed arrows from tooltips to nodes
- Selected unreachable nodes have lighter styling (0.6 opacity)

### Tooltip System
| Feature     | Description                           |
| ----------- | ------------------------------------- |
| Hover       | Shows node details at node position   |
| Click       | Persists tooltip, selects node        |
| CTRL+Click  | Multi-select, each node gets tooltip  |
| Drag        | Reposition tooltips, arrows follow    |
| Type Filter | Hides all tooltips when filter active |

### TypeScript Migration
- Full migration to TypeScript with strict mode
- Modular ES6 architecture (14 module files)
- Vitest unit testing configured

### Singular/Universal Mode Fix
- Fixed node ID generation to respect `config.is_singular()`
- All node types (CPE, CVE, CWE, TI, VC) now correctly switch modes
- Settings modal properly triggers graph rebuild

### Reachability Filter Fix
- Fixed BFS race condition for multi-predecessor nodes
- Changed from backward unreachability propagation to forward reachability propagation
- Added 3 new browser tests for reachability scenarios

### Test Infrastructure
- Python: 66 tests, 94% coverage
- TypeScript: 9 unit tests
- Playwright: 37 browser tests
- Added `TestSingularUniversalMode` class (6 tests)
- Added `TestReachabilityFiltering` class (9 tests)
- Updated `TestNodeSelection` class (3 tooltip tests)
