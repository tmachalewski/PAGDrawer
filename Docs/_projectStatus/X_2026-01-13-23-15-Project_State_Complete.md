# PAGDrawer - Project State Overview
**Date:** 2026-01-13 23:15
**Status:** Feature Complete (Tooltip System & Graph Logic)

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
| Node Type | Default  | Singular Logic             | Universal Logic |
| --------- | -------- | -------------------------- | --------------- |
| CPE       | singular | Per-Host                   | Global Unique   |
| CVE       | singular | Per-Host                   | Global Unique   |
| CWE       | singular | Per-Weakness ID            | Global Unique   |
| TI        | singular | Per-CWE                    | Global Unique   |
| VC        | singular | Per-Host (Converged state) | Global Unique   |

### 4. Interactive Tooltips (COMPLETED)
- **Hover**: Shows node details at node position.
- **Persistence**: Clicking a node "pins" the tooltip.
- **Multi-Selection**: CTRL+Click to select multiple nodes, each gets a separate pinned tooltip.
- **Draggable**: Tooltips can be dragged anywhere on screen.
- **Detached Positioning**: Dragged tooltips maintain absolute screen position during zoom/pan (no "jumping").
- **Visuals**: Dashed SVG arrows connect tooltips to nodes; active tooltip pops to front (z-index).

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

## Recent Milestones (Jan 13, 2026)

### ✅ Tooltip System Perfection
- **Position Persistence**: Solved the "jumping tooltip" issue by storing absolute screen coordinates for dragged tooltips, completely detaching them from graph zoom/pan logic.
- **TI Node Bug Fix**: Fixed critical issue where clicking TI nodes (e.g., `TI:Execute...`) dimmed the whole graph. Root cause was `CSS.escape()` failing on complex IDs; switched to reliable `cy.getElementById()`.
- **Z-Index Management**: Hovering over any tooltip now brings it to the front (`z-index: 10100`), preventing overlap issues in multi-select scenarios.
- **Styling Refinements**: Updated technical text ("Cannot exploit until...") and added visual cues (brighter borders on hover).

### ✅ Graph Logic Validation
- Confirmed "Singular (Per-Host)" grouping logic for VC nodes: multiple attack vectors (e.g., SQLi, CmdInjection) correctly converge into a single `AV:L` capability node per host, reducing graph clutter while maintaining logical correctness.
