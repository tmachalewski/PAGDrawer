# 2026-01-19 22:40 - Scan Selection Feature & Visibility Fix

## Overview

Implemented the Trivy scan selection feature allowing users to select specific scans for graph generation, and fixed visibility persistence after rebuild.

---

## Features Implemented

### Backend Changes (`src/viz/app.py`)

**TrivyScan Dataclass**
```python
@dataclass
class TrivyScan:
    id: str           # UUID
    name: str         # From ArtifactName
    filename: str
    uploaded_at: datetime
    vuln_count: int
    data: Dict[str, Any]
```

**New Endpoints:**
- `GET /api/data/scans` - List all uploaded scans with metadata
- `DELETE /api/data/scans/{scan_id}` - Remove specific scan
- Modified `/api/data/rebuild` to accept `scan_ids` query parameter

### Frontend Changes

| File            | Changes                                                     |
| --------------- | ----------------------------------------------------------- |
| `types.ts`      | Added `ScanInfo`, `ScansResponse` interfaces                |
| `api.ts`        | Added `getScans()`, `deleteScan()`, updated `rebuildData()` |
| `index.html`    | Scan selector dropdown, scan list with delete buttons       |
| `styles.css`    | Styling for `.scan-select`, `.scan-item`                    |
| `dataSource.ts` | List refresh, selector population, delete handling          |

---

## Challenges Encountered

### 1. Visibility State Lost on Rebuild

**Problem:** When rebuilding the graph, hidden node types would become visible again because `initCytoscape()` creates a fresh graph instance.

**Solution:** Added call to `reapplyHiddenTypes()` after graph initialization:
```typescript
setTimeout(() => {
    runLayout();
    reapplyHiddenTypes();  // <-- Fix
}, 100);
```

The `filter.ts` module already had the `reapplyHiddenTypes()` function that tracks hidden types in a module-level `Set` and re-hides them after graph rebuild.

### 2. CORS Issues During Browser Testing

**Problem:** Browser subagent couldn't fetch example files from `http://localhost:8000/examples/` due to CORS restrictions when running from `http://localhost:3000`.

**Workaround:** Used same-origin requests via the backend's `/docs` endpoint, and verified the scans were already loaded from prior testing.

### 3. Global Function Exposure

**Problem:** Delete buttons use inline `onclick` handlers which can't access TypeScript module functions directly.

**Solution:** Exposed `deleteScanItem` to the global `window` object:
```typescript
// main.ts
declare global {
    interface Window {
        deleteScanItem: (scanId: string, event: Event) => Promise<void>;
    }
}
window.deleteScanItem = deleteScanItem;
```

---

## Test Results

| Test Case                           | Result |
| ----------------------------------- | ------ |
| Upload multiple scans               | ✅      |
| Scan selector shows "All Scans (N)" | ✅      |
| Individual scan selection           | ✅      |
| Delete scan removes from list       | ✅      |
| Visibility persists on rebuild      | ✅      |
| Rebuild uses selected scan IDs      | ✅      |

### Screenshots

**Graph Statistics View**
![Initial state](file:///C:/Users/Tomek%20Machalewski/.gemini/antigravity/brain/497c1344-437c-47fa-a598-9aa1c117c322/initial_scan_selector_1768859656705.png)

**Scan Selector UI**
![Scan selector](file:///C:/Users/Tomek%20Machalewski/.gemini/antigravity/brain/497c1344-437c-47fa-a598-9aa1c117c322/final_test_result_1768859758332.png)

---

## Files Modified

- `src/viz/app.py` - TrivyScan dataclass, scan endpoints
- `frontend/js/types.ts` - ScanInfo interface
- `frontend/js/services/api.ts` - getScans, deleteScan, rebuildData
- `frontend/index.html` - Scan selector UI
- `frontend/css/styles.css` - Scan selector styles
- `frontend/js/features/dataSource.ts` - Scan management + visibility fix
- `frontend/js/main.ts` - Global function exposure

---

## Recording

![Scan Selection Test](file:///C:/Users/Tomek%20Machalewski/.gemini/antigravity/brain/497c1344-437c-47fa-a598-9aa1c117c322/scan_selection_test_1768859529649.webp)
