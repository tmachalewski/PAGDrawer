# Frontend Refactoring - ES6 Modules Migration
**Date:** 2026-01-11 22:03

## Summary
Refactored the monolithic `frontend/index.html` into a modular ES6 architecture, separating concerns into dedicated CSS and JavaScript modules.

---

## Before vs After

| Metric              | Before      | After       |
| ------------------- | ----------- | ----------- |
| **index.html**      | 1,309 lines | 207 lines   |
| **Total Files**     | 1           | 14          |
| **Architecture**    | Monolithic  | Modular ES6 |
| **Testability**     | Difficult   | Per-module  |
| **Maintainability** | Low         | High        |

---

## New File Structure

```
frontend/
├── index.html                    # Minimal HTML structure (207 lines)
├── css/
│   └── styles.css                # Extracted CSS (303 lines)
└── js/
    ├── main.js                   # Entry point, initialization
    ├── config/
    │   └── constants.js          # Colors, Cytoscape styles
    ├── services/
    │   └── api.js                # Backend communication
    ├── graph/
    │   ├── core.js               # Cytoscape instance management
    │   ├── layout.js             # Layout algorithms
    │   └── events.js             # Click/keyboard handlers
    ├── features/
    │   ├── filter.js             # Node type filtering
    │   ├── environment.js        # UI/AC environment cascade filter
    │   ├── hideRestore.js        # Hide/restore with bridge edges
    │   └── exploitPaths.js       # Exploit path highlighting
    └── ui/
        ├── sidebar.js            # Stats panel updates
        └── modal.js              # Settings modal
```

---

## Module Details

### `/js/config/constants.js`
Exports:
- `nodeColors` - Color mapping for each node type
- `edgeColors` - Color mapping for each edge type
- `getCytoscapeStyles()` - Returns Cytoscape.js style definitions

### `/js/services/api.js`
Exports:
- `fetchGraph()` - GET /api/graph
- `fetchStats()` - GET /api/stats
- `fetchConfig()` - GET /api/config
- `updateConfig(config)` - POST /api/config

### `/js/graph/core.js`
Exports:
- `getCy()` - Returns Cytoscape instance
- `initCytoscape(elements)` - Initialize graph
- `destroyCytoscape()` - Clean up instance

### `/js/graph/layout.js`
Exports:
- `changeLayout(name)` - Switch layout algorithm
- `runLayout()` - Execute current layout
- `fitView()` - Fit graph to viewport
- `getColumnPositions()` - Column positions for dagre

### `/js/graph/events.js`
Exports:
- `setupEventHandlers()` - Initialize all event listeners

### `/js/features/filter.js`
Exports:
- `setupFilterButtons()` - Initialize filter button listeners
- `filterByType(type)` - Filter nodes by type

### `/js/features/environment.js`
Exports:
- `applyEnvironmentFilter()` - Apply UI/AC cascade filtering
- `setupEnvironmentListeners()` - Initialize dropdown listeners

### `/js/features/hideRestore.js`
Exports:
- `hideSelectedNodes()` - Hide nodes with bridge edges
- `restoreAllNodes()` - Restore all hidden nodes
- `getHiddenCount()` - Count of hidden elements

### `/js/features/exploitPaths.js`
Exports:
- `toggleExploitPaths()` - Toggle exploit path view
- `isExploitPathsActive()` - Check current state

### `/js/ui/sidebar.js`
Exports:
- `updateStats(stats)` - Update stats panel
- `showLoading()` / `hideLoading()` - Loading overlay control
- `showError(message)` - Display error message

### `/js/ui/modal.js`
Exports:
- `openSettings()` - Open modal with current config
- `closeSettings()` - Close modal
- `saveSettings()` - Save and rebuild graph

---

## Backend Changes

### `/src/viz/app.py`
Added static file mounts for CSS and JS directories:

```python
# Mount CSS directory
css_dir = frontend_dir / "css"
if css_dir.exists():
    app.mount("/css", StaticFiles(directory=str(css_dir)), name="css")

# Mount JS directory  
js_dir = frontend_dir / "js"
if js_dir.exists():
    app.mount("/js", StaticFiles(directory=str(js_dir)), name="js")
```

---

## How ES6 Modules Work

### index.html loads main.js as a module:
```html
<script type="module" src="js/main.js"></script>
```

### main.js imports all modules:
```javascript
import { fetchGraph, fetchStats } from './services/api.js';
import { initCytoscape } from './graph/core.js';
import { runLayout } from './graph/layout.js';
// ... more imports
```

### Global functions for HTML onclick handlers:
```javascript
window.changeLayout = changeLayout;
window.runLayout = runLayout;
window.openSettings = openSettings;
// ... exposed to global scope
```

---

## Test Results

All tests pass after refactoring:

| Test File                     | Tests   | Status         |
| ----------------------------- | ------- | -------------- |
| test_schema.py                | 17      | ✅ Pass         |
| test_config.py                | 10      | ✅ Pass         |
| test_consensual_matrix.py     | 15      | ✅ Pass         |
| test_builder.py               | 26      | ✅ Pass         |
| test_api.py                   | 14      | ✅ Pass         |
| test_frontend.py (Playwright) | 27      | ✅ Pass         |
| **Total**                     | **118** | **✅ All Pass** |

---

## Benefits of This Refactoring

1. **Separation of Concerns** - CSS, HTML, and JS are separate
2. **Modularity** - Each feature in its own file
3. **Testability** - Individual modules can be unit tested
4. **Maintainability** - Easy to find and modify code
5. **Reusability** - Modules can be imported where needed
6. **Tree Shaking** - Unused code can be eliminated
7. **IDE Support** - Better autocomplete and navigation
8. **Collaboration** - Multiple devs can work on different modules

---

## Migration Notes

- All functionality preserved
- No breaking changes to the API
- Existing workflows continue to work
- Hot reload still works with uvicorn --reload
