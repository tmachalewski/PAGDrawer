# E2E Test Fixes & UI Consolidation

**Date:** 2026-01-15
**Status:** Completed

---

## Summary

Two main improvements made today:

1. **Fixed E2E Test Timing Issues** - All 37 Playwright tests now pass reliably
2. **Merged Node Types Legend with Filter Buttons** - Consolidated UI to save sidebar space

---

## 1. E2E Test Fixes

### Problem
14 of 37 Playwright E2E tests were failing with errors:
- `TypeError: cy.nodes is not a function`
- `TypeError: cy.getElementById is not a function`

### Root Causes
1. **Wrong server port**: Tests were hitting FastAPI (port 8000) which serves raw `.ts` files. Browsers can't execute TypeScript directly.
2. **Unreliable waits**: Tests used fixed `wait_for_timeout(2000)` instead of waiting for Cytoscape to initialize.

### Solution
1. Changed `BASE_URL` from port 8000 to **port 3000** (Vite dev server handles TypeScript transpilation)
2. Added `wait_for_cytoscape()` helper function:
```python
def wait_for_cytoscape(page: Page, timeout: int = 10000) -> None:
    page.wait_for_function(
        """() => {
            const cy = window.cy || (window.getCy ? window.getCy() : null);
            return cy && typeof cy.nodes === 'function' && cy.nodes().length > 0;
        }""",
        timeout=timeout
    )
```
3. Replaced all `wait_for_timeout()` calls with proper wait conditions

### Result
All 146 tests pass (109 backend + 37 frontend)

---

## 2. UI Consolidation: Merged Legend & Filters

### Before
Two separate sections in sidebar:
- "Node Types" legend (colored dots with labels)
- "Filter by Type" buttons (separate button group)

### After
Single unified section:
- Legend items are now clickable filter buttons
- Each button has colored dot + type name
- "All Types" button at top with gradient dot
- Subtle hint text "(click to filter)"

### Changes
- `frontend/index.html`: Converted legend items to `<button>` elements with `data-type` attributes
- `frontend/css/styles.css`: Added `.legend-filter-btn` styling

### Behavior
Same as before - clicking filters the graph to show only that node type. "All Types" resets.

---

## Commits

```
ddb98c4 feat(ui): merge Node Types legend with filter buttons
636230b fix: E2E test timing and configuration issues
bd7efc2 initial commit
```

---

## Testing Notes

To run E2E tests, need **both servers**:
```bash
# Terminal 1: Backend API
python -m uvicorn src.viz.app:app --port 8000

# Terminal 2: Frontend (Vite)
cd frontend && npm run dev

# Terminal 3: Tests
python -m pytest tests/test_frontend.py -v
```
