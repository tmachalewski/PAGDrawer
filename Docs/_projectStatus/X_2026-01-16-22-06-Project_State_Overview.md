# PAGDrawer - Project State Overview
**Date:** 2026-01-16 22:06
**Status:** Feature Complete (Granular Grouping & Visibility Toggles)

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
| BRIDGE         | any → any       | Visual connector (hidden nodes) |

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

### 3. Granular Grouping Sliders (NEW)
Each node type has a slider controlling how nodes are grouped:

| Node Type | Slider Options                      |
| --------- | ----------------------------------- |
| CPE       | ATTACKER, HOST                      |
| CVE       | ATTACKER, HOST, CPE                 |
| CWE       | ATTACKER, HOST, CPE, CVE            |
| TI        | ATTACKER, HOST, CPE, CVE, CWE       |
| VC        | ATTACKER, HOST, CPE, CVE, CWE, TI   |

- **ATTACKER** = universal (one shared node globally)
- **Immediate predecessor** = most granular (per-parent)
- Sliders are vertically aligned so the same grouping level appears in the same column
- Settings persist after save and graph rebuild

### 4. Visibility Toggles (NEW)
- **Toggle Buttons**: 👁 button next to each node type filter
- **Bridge Edges**: When hiding a type, cyan dashed lines connect predecessors to successors
- **Restore All**: Restores all hidden types with original edges
- **Settings Persistence**: Hidden types survive granularity setting changes
- **Two-Pass Restoration**: Ensures edges between multiple restored types are preserved

### 5. Hide Selected / Restore All
- **Hide Selected**: Remove individual nodes, creating bridge edges
- **Restore All**: Bring back all hidden nodes and reset visibility toggles
- **Bridge Styling**: Cyan dashed lines (opacity 0.5)

### 6. Interactive Tooltips
- **Hover**: Shows node details at node position
- **Persistence**: Clicking pins the tooltip
- **Multi-Selection**: CTRL+Click for multiple pinned tooltips
- **Draggable**: Tooltips can be dragged anywhere
- **Detached Positioning**: Dragged tooltips maintain absolute position during zoom/pan

---

## File Structure

```
PAGDrawer/
├── frontend/
│   ├── index.html              # Main HTML (toggles, sliders)
│   ├── vite.config.ts          # Vite + Vitest config
│   ├── tsconfig.json           # TypeScript strict config
│   ├── css/
│   │   └── styles.css          # Styling (toggles, grid layout)
│   └── js/
│       ├── main.ts             # Entry point
│       ├── types.ts            # TypeScript definitions
│       ├── types.test.ts       # Type tests
│       ├── config/constants.ts # Colors, Cytoscape styles
│       ├── services/api.ts     # Backend communication
│       ├── graph/{core,layout,events}.ts
│       ├── features/
│       │   ├── filter.ts       # Node filtering + visibility toggles
│       │   ├── environment.ts  # UI/AC filtering
│       │   ├── hideRestore.ts  # Hide Selected feature
│       │   └── exploitPaths.ts # Exploit path highlighting
│       └── ui/{sidebar,modal,tooltip}.ts
├── src/
│   ├── core/
│   │   ├── schema.py           # NodeType, EdgeType enums
│   │   ├── config.py           # Graph config + grouping hierarchy
│   │   └── consensual_matrix.py
│   ├── data/mock_data.py       # Sample data
│   ├── graph/builder.py        # KnowledgeGraphBuilder
│   └── viz/app.py              # FastAPI application
├── tests/
│   ├── test_builder.py         # Graph builder tests
│   ├── test_api.py             # API endpoint tests
│   ├── test_config.py          # Config/grouping tests
│   ├── test_schema.py          # Schema tests
│   └── test_frontend.py        # 67 Playwright E2E tests
└── Docs/
    ├── _dailyNotes/            # Development logs (19 notes)
    ├── _projectStatus/         # Project snapshots
    └── _PythonTestingStandards.md
```

---

## Test Coverage

### Python Backend
| Module                          | Coverage |
| ------------------------------- | -------- |
| `src/core/config.py`            | 100%     |
| `src/core/consensual_matrix.py` | 98%      |
| `src/core/schema.py`            | 100%     |
| `src/graph/builder.py`          | 94%      |
| `src/viz/app.py`                | 95%      |
| **TOTAL**                       | **96%**  |

### Test Suites
| Suite                | Tests   | Framework         |
| -------------------- | ------- | ----------------- |
| Python Backend       | 101     | pytest            |
| TypeScript Unit      | 9       | Vitest            |
| Playwright E2E       | 67      | pytest-playwright |
| **TOTAL**            | **177** |                   |

### E2E Test Classes
| Class                    | Tests | Description                    |
| ------------------------ | ----- | ------------------------------ |
| TestBasicNavigation      | 5     | Page load, graph rendering     |
| TestFilterButtons        | 6     | Node type filtering            |
| TestEnvironmentSettings  | 8     | UI/AC filtering                |
| TestTooltipInteraction   | 16    | Hover, click, drag, z-index    |
| TestReachabilityFiltering| 9     | Host reachability dimming      |
| TestHideRestore          | 8     | Hide selected, restore all     |
| TestGranularGrouping     | 5     | Slider functionality           |
| TestVisibilityToggle     | 10    | Visibility toggle feature      |

---

## Recent Milestones (Jan 16, 2026)

### ✅ Granular Grouping Sliders
- Replaced binary singular/universal dropdowns with multi-position sliders
- Grid-based UI with aligned columns across all node types
- Backend supports full grouping hierarchy: ATTACKER → HOST → CPE → CVE → CWE → TI
- Backward compatible with legacy "singular"/"universal" values

### ✅ Visibility Toggle Feature
- Added 👁 toggle buttons for each node type
- Bridge edges (cyan dashed) maintain graph connectivity when hiding types
- Two-pass restoration fixes edge loss bug on multi-type restore
- Settings persistence preserves hidden state across graph rebuilds
- 10 comprehensive E2E tests covering edge cases

### ✅ Test Infrastructure
- 177 total tests (101 backend + 9 unit + 67 E2E)
- 96% backend code coverage
- All tests pass reliably

---

## Technical Notes

### Two-Layer Attack Model
The system models a two-layer network:
- **L1 (External)**: Hosts directly reachable from ATTACKER
- **L2 (Internal)**: Hosts reachable only via pivot from L1

Nodes are "universal within layer" - for example, with ATTACKER-level grouping, there's one TI node per layer (external and internal).

### Bridge Edge Pattern
When nodes are hidden (via Hide Selected or Visibility Toggle):
1. Store node data and incident edges
2. Remove nodes from graph
3. Create bridge edges connecting predecessors to successors
4. Style: cyan (#00ffff), dashed, 50% opacity

### State Management (Frontend)
```typescript
// Visibility toggle state
const hiddenTypes: Set<string> = new Set();
const hiddenByType: Map<string, HiddenTypeData> = new Map();
const typeBridgeEdges: Map<string, EdgeSingular[]> = new Map();

// Functions
toggleTypeVisibility(type)  // Toggle hide/show
hideNodeType(type)          // Hide + create bridges
showNodeType(type)          // Restore + remove bridges
resetVisibility()           // Restore all (two-pass)
reapplyHiddenTypes()        // Re-hide after graph rebuild
```

---

## API Endpoints

| Method | Endpoint      | Description                  |
| ------ | ------------- | ---------------------------- |
| GET    | /graph        | Fetch full graph data        |
| POST   | /graph/config | Update graph configuration   |
| GET    | /config       | Get current configuration    |
| GET    | /stats        | Get node/edge statistics     |

---

## Running the Project

```bash
# Start backend
cd PAGDrawer
python -m uvicorn src.viz.app:app --reload --port 8000

# Start frontend (separate terminal)
cd frontend
npm run dev

# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=src --cov-report=term-missing

# Run single test class
python -m pytest tests/test_frontend.py::TestVisibilityToggle -v
```

---

## Known Limitations

1. **Visibility state not persisted**: Hidden types reset on page refresh
2. **Mock data only**: No real vulnerability database integration yet
3. **Single user**: No multi-user or session management

---

## Future Enhancements (Potential)

- Real vulnerability data integration (NVD, CVE feeds)
- Session persistence for visibility/filter state
- Export graph to various formats (PNG, SVG, JSON)
- Attack path analysis with probability scoring
- Multi-user collaboration features
