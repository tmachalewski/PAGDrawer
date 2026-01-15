# PAGDrawer Project State - TypeScript Migration Complete

**Date:** 2026-01-12  
**Status:** ✅ TypeScript migration complete with strict mode

## Overview

PAGDrawer has been fully migrated from JavaScript to TypeScript with Vite as the build tool. All 33 Playwright frontend tests pass.

## Architecture

### Frontend Stack
| Component         | Technology               |
| ----------------- | ------------------------ |
| **Language**      | TypeScript (strict mode) |
| **Build Tool**    | Vite 5.4                 |
| **Graph Library** | Cytoscape.js             |
| **Dev Server**    | `http://localhost:3000`  |

### Backend Stack
| Component     | Technology              |
| ------------- | ----------------------- |
| **Framework** | FastAPI                 |
| **Server**    | Uvicorn                 |
| **Port**      | `http://localhost:8000` |

## File Structure

```
frontend/
├── index.html              # Entry point (loads main.ts)
├── package.json            # npm dependencies
├── tsconfig.json           # TypeScript config (strict: true)
├── vite.config.ts          # Vite with API proxy
├── css/
│   └── styles.css
└── js/
    ├── main.ts             # Entry point
    ├── types.ts            # Shared type definitions
    ├── config/
    │   └── constants.ts    # Colors, styles
    ├── graph/
    │   ├── core.ts         # Cytoscape instance
    │   ├── layout.ts       # Layout algorithms
    │   └── events.ts       # Event handlers
    ├── features/
    │   ├── filter.ts       # Type filtering
    │   ├── environment.ts  # UI/AC filtering + reachability
    │   ├── hideRestore.ts  # Node hiding with bridges
    │   └── exploitPaths.ts # Exploit path highlighting
    ├── services/
    │   └── api.ts          # API calls
    └── ui/
        ├── sidebar.ts      # Stats panel
        ├── modal.ts        # Settings modal
        └── tooltip.ts      # Dimmed node tooltips
```

## Key Features

### 1. Graph Visualization
- 175 nodes, 218 edges (typical configuration)
- Dagre, Breadthfirst, Cose, Circle layouts
- Node types: HOST, CPE, CVE, CWE, TI, VC, ATTACKER

### 2. Environment Filtering
- User Interaction (UI:N/R) filtering
- Attack Complexity (AC:L/H) filtering
- Cascade filtering through CWE → TI → VC chain

### 3. Reachability Filtering
- Dims hosts not reachable from ATTACKER
- BFS propagation to downstream nodes
- Tooltip explains why nodes are dimmed

### 4. Hide/Restore
- Hide selected nodes with bridge edges
- Keyboard shortcut: `H`
- Full restore functionality

### 5. Exploit Paths
- Highlights paths to terminal nodes (EX:Y)
- Backward BFS from terminals

## Development Commands

```bash
# Start backend
cd PAGDrawer
uvicorn src.viz.app:app --reload --host 0.0.0.0 --port 8000

# Start frontend (Vite)
cd frontend
npm run dev

# Run frontend tests
$env:PYTEST_BASE_URL='http://localhost:3000'
pytest tests/test_frontend.py -v

# TypeScript check
cd frontend
npx tsc --noEmit
```

## Test Coverage

**33 Playwright tests** covering:
- Graph loading and display
- Environment filtering (UI/AC)
- Node selection and details
- Layout controls
- Exploit paths toggle
- Settings modal
- Hide/Restore functionality
- Filter buttons
- Reachability filtering (6 tests)

## Recent Changes (This Session)

1. **TypeScript Migration** - All 15 JS modules converted to TS
2. **Vite Integration** - Dev server with API proxy
3. **Strict Mode** - `strict: true` with all errors resolved
4. **Type Safety** - Proper Cytoscape types throughout

## Notes

- Vite proxies `/api/*` requests to FastAPI backend
- `index.html` loads `main.ts` directly (Vite handles TS)
- Window globals declared for inline HTML event handlers
- `.toArray() as NodeSingular[]` pattern for Cytoscape collection iteration
