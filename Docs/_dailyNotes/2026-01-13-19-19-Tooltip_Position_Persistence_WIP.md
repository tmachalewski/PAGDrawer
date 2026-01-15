# Tooltip Position Persistence - Approaches Tried
**Date:** 2026-01-13 19:19
**Status:** ✅ Completed

## Problem Statement
When a user drags a tooltip to a custom position and then zooms in/out, the tooltip should maintain its relative position to the node. Currently, the tooltip resets to its default position when hovering over a node after zooming.

---

## Approaches Tried

### Approach 1: Absolute Position Storage ❌
**Implementation:**
```typescript
let customPositions: Map<string, { left: number; top: number }> = new Map();
```
- Store the absolute screen coordinates when tooltip is dragged
- Restore these coordinates when tooltip is recreated

**Result:** Failed - Positions reset on hover because `updateAllTooltips()` recreates the DOM elements

---

### Approach 2: Offset-Based Storage ❌
**Implementation:**
```typescript
let customOffsets: Map<string, { dx: number; dy: number }> = new Map();
```
- Calculate offset from node's rendered position: `offset = tooltipPos - nodeScreenPos`
- Store offset in pixels relative to node center
- On tooltip recreation, apply offset to node's current rendered position

**Result:** Partially worked - Tooltip stays in place on hover after drag, but...

---

### Approach 3: Viewport Change Repositioning ❌
**Implementation:**
```typescript
cy.on('viewport', handleViewportChange);
// Reposition all tooltips based on stored offsets
```
- Listen to viewport changes (zoom/pan)
- Reposition dragged tooltips using: `newPos = nodeScreenPos + storedOffset`

**Result:** Failed - Tooltips moved unexpectedly (only horizontally?) on zoom

---

### Approach 4: Only Reposition Dragged Tooltips ❌
**Implementation:**
```typescript
if (!customOffset) return; // Skip non-dragged tooltips
```
- Only reposition tooltips that have stored offsets
- Leave non-dragged tooltips at their original positions

**Result:** Failed - Still caused movement during zoom

---

### Approach 5: No Viewport Repositioning ❌
**Implementation:**
```typescript
function handleViewportChange(): void {
    updateArrows(); // Only update arrows, not tooltip positions
}
```
- Don't reposition tooltips on viewport change at all
- Only update arrows to keep pointing at nodes

**Result:** Current state - Tooltips stay fixed during zoom, BUT reset on hover

---

## Root Cause Analysis

The core issue is that `updateAllTooltips()` **recreates all tooltip DOM elements** every time:
1. User hovers over any node → `handleNodeMouseOver()` called
2. `updateAllTooltips()` wipes `tooltipContainer.innerHTML`
3. New tooltip elements created with `createTooltipHTML()`
4. `positionTooltipByIndex()` called for each tooltip
5. If offset exists, restored position is calculated

**The problem:** After zooming, the offset calculation uses the NEW node rendered position, which has changed. The offset was calculated at the OLD zoom level.

---

## Potential Solutions to Try

### Solution A: Store Offset in Model Coordinates
Instead of storing pixel offsets, store offsets relative to the graph's model coordinates (not rendered coordinates). This would require:
- Convert screen position to model position when storing
- Convert model offset back to screen position when restoring

### Solution B: Don't Recreate Existing Tooltips
Instead of destroying and recreating tooltip DOM on every hover:
- Only create new tooltips for nodes that don't already have one
- Only destroy tooltips for nodes that are no longer in the display set
- Update content of existing tooltips in place

### Solution C: Store Screen Position and Ignore Node Position ✅ WORKED!
After a tooltip is dragged, completely disconnect it from node positioning:
- Mark tooltip as "detached" 
- Store absolute screen position in `draggedPositions` Map
- Don't recalculate position at all, just restore stored coordinates

**Implementation:**
```typescript
let draggedPositions: Map<string, { left: number; top: number }> = new Map();

// On drag:
draggedPositions.set(nodeId, { left: newLeft, top: newTop });

// On position:
const draggedPos = draggedPositions.get(nodeId);
if (draggedPos) {
    tooltipBox.style.left = draggedPos.left + 'px';
    tooltipBox.style.top = draggedPos.top + 'px';
    return;
}
```

---

## Files Modified
- `frontend/js/ui/tooltip.ts`

## Current State
- Custom offsets are stored in `customOffsets` Map
- `handleViewportChange()` only updates arrows
- Tooltips reset to default position when hovering after zoom
