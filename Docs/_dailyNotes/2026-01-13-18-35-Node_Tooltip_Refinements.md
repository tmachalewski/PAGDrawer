# Node Tooltip Refinements
**Date:** 2026-01-13 18:35

## Summary
Refined the hover tooltip behavior based on user feedback. Added fixed positioning relative to node center, persistence on selection, and viewport tracking.

---

## Changes

### 1. Fixed Position (Not Following Cursor)
- Tooltip now positions relative to **node center** instead of following mouse
- Removed `mousemove` handler
- Uses `node.renderedPosition()` for stable positioning

### 2. Persistence on Selection
- **Click** a node → tooltip stays visible
- **Hover** other nodes → tooltip updates temporarily, returns to selected node on mouseout
- **Click background** → clears selection, hides tooltip

### 3. Viewport Tracking
- Added `viewport` event listener
- Tooltip position updates when **zooming** or **panning**
- Tooltip stays anchored to node position during all viewport changes

---

## Implementation Details

### New State Variables
```typescript
let selectedNode: NodeSingular | null = null;
let hoveredNode: NodeSingular | null = null;
```

### Event Handlers Added
| Event               | Handler                                             |
| ------------------- | --------------------------------------------------- |
| `tap` on node       | `handleNodeClick` - sets selectedNode               |
| `tap` on background | `handleBackgroundClick` - clears selection          |
| `viewport`          | `updateTooltipForCurrentNode` - repositions tooltip |

### Logic Flow
```
mouseover → show tooltip for hovered node
mouseout  → if selected, show selected node's tooltip; else hide
click     → set selected, persist tooltip
zoom/pan  → update position for current node
bg click  → clear all, hide tooltip
```

---

## File Modified
- `frontend/js/ui/tooltip.ts`

---

## Behavior Summary

| Action                 | Result                                           |
| ---------------------- | ------------------------------------------------ |
| Hover node             | Tooltip appears at node center                   |
| Move mouse within node | Tooltip stays fixed                              |
| Click node             | Tooltip persists after mouseout                  |
| Hover different node   | Tooltip updates, returns to selected on mouseout |
| Zoom/Pan               | Tooltip follows node position                    |
| Click background       | Clears selection, hides tooltip                  |
