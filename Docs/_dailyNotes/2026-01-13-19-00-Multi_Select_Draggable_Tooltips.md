# Multi-Select Tooltips with Drag & Arrows
**Date:** 2026-01-13 19:00

## Summary
Major enhancement to the node tooltip system: moved from sidebar to hover tooltips, added CTRL multi-select, draggable tooltip windows, SVG arrows pointing to nodes, and improved styling for selected unreachable nodes.

---

## Features Implemented

### 1. Hover Tooltip (Replaced Sidebar Panel)
- Tooltip appears when hovering over any node
- Shows node details: id, label, type, and other properties
- Warning section for dimmed nodes (unreachable/env-filtered)
- Removed `Node Details` section from sidebar

### 2. Selection Persistence
- Click node → tooltip stays visible
- Click background → clears selection and hides tooltip

### 3. CTRL Multi-Select
- **Click** → single selection
- **CTRL+Click** → toggle node in/out of selection
- Each selected node gets its own tooltip box
- Highlights work with multiple selected nodes

### 4. Draggable Tooltips
- Click and drag any tooltip to reposition
- Tooltips stay where you put them
- Drag handle indicator at top of each tooltip

### 5. SVG Arrows
- Dashed line from tooltip corner to node center
- Small circle indicator at tooltip anchor point
- Arrows update in real-time:
  - When dragging tooltip
  - When zooming/panning graph
  - When viewport changes

### 6. Selected Unreachable Nodes
- Opacity increases from 0.3 → 0.6 when selected
- White border (4px) for visibility
- Uses custom `.node-selected` class

---

## Files Modified

| File                              | Changes                                        |
| --------------------------------- | ---------------------------------------------- |
| `frontend/js/ui/tooltip.ts`       | Complete rewrite - multi-select, drag, arrows  |
| `frontend/js/graph/events.ts`     | Removed tap handlers (moved to tooltip.ts)     |
| `frontend/js/config/constants.ts` | Added `.unreachable.node-selected` style       |
| `frontend/css/styles.css`         | Tooltip box styles, drag cursor, header        |
| `frontend/index.html`             | Removed Node Details sidebar section           |
| `tests/test_frontend.py`          | Updated TestNodeSelection for tooltip behavior |

---

## Technical Details

### State Management
```typescript
let selectedNodes: Set<string> = new Set();
let hoveredNode: NodeSingular | null = null;
let isFilterActive: boolean = false;
let currentNodes: NodeSingular[] = [];  // For arrow updates
```

### SVG Arrow System
- Container: `#tooltip-arrows` SVG element (full-screen, pointer-events: none)
- Elements per tooltip: `<line>` (dashed) + `<circle>` (anchor point)
- Updates on: drag, viewport change, selection change

### Drag Implementation
- `mousedown` on tooltip → track start position
- `mousemove` on document → update position, redraw arrows
- `mouseup` on document → end drag

---

## Behavior Matrix

| Action             | Result                             |
| ------------------ | ---------------------------------- |
| Hover node         | Tooltip appears at node            |
| Click node         | Selects node, tooltip persists     |
| CTRL+Click         | Toggle multi-select                |
| Drag tooltip       | Repositions, arrow follows         |
| Zoom/Pan           | Arrows update to follow nodes      |
| Type filter active | All tooltips hidden                |
| Click background   | Clear selection, hide all          |
| Select unreachable | Node becomes lighter (0.6 opacity) |

---

## CSS Classes Added

| Class                 | Purpose                         |
| --------------------- | ------------------------------- |
| `.tooltip-box`        | Individual tooltip container    |
| `.tooltip-header`     | Drag handle indicator           |
| `.tooltip-box:active` | Grabbing cursor                 |
| `.node-selected`      | Custom class for selected nodes |
