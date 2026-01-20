# 2026-01-20 10:40 - Bridge Edges, Edge Restoration, and Dynamic Stats

## Overview

Three significant improvements to graph visualization and interaction:
1. **Bridge Edge Coloring** - Dynamic colors based on hidden edge types
2. **Edge Restoration Bug Fix** - Edges no longer disappear when toggling visibility
3. **Dynamic Graph Stats** - Settings modal shows live node/edge counts

---

## 1. Bridge Edge Coloring

**Feature**: Bridge edges (created when hiding node types) now display colored based on the edge types they represent.

### Implementation

Added `computeBridgeColor()` function in `filter.ts`:
- Collects edge types from hidden edges
- Averages their colors from `edgeColors` map
- Brightens the result (40% towards white)
- Boosts saturation for visibility

```typescript
function computeBridgeColor(edgeTypes: string[]): string {
    // Average RGB values from edgeColors
    // Brighten: r = r + (255 - r) * 0.4
    // Boost saturation for visibility
}
```

### Cytoscape Style Update

```typescript
{
    selector: 'edge[?isBridge]',
    style: {
        'line-color': (ele) => ele.data('bridgeColor') || '#00ffff',
        'target-arrow-color': (ele) => ele.data('bridgeColor') || '#00ffff'
    }
}
```

**Result**: Hiding CVE shows orange-yellow bridges (HAS_VULN edge color), hiding CWE shows green bridges (IS_INSTANCE_OF), etc.

---

## 2. Edge Restoration Bug Fix

**Problem**: Edges would permanently disappear when:
1. Hide CVE → Hide CWE
2. Show CVE (CVE↔CWE edges skipped because CWE still hidden)
3. Show CWE → **Edges lost forever**

### Root Cause

Edges were stored per-type in `hiddenByType`. When edges connected two hidden types, they were stored in both. Restoration only checked the current type's storage.

### Solution

Introduced **global edge storage**:

```typescript
// Global edge storage - prevents duplicates
const globalHiddenEdges: Map<string, ElementDefinition> = new Map();
```

**In `hideNodeType()`**:
```typescript
if (!globalHiddenEdges.has(edgeId)) {
    globalHiddenEdges.set(edgeId, edge.json());
}
```

**In `showNodeType()`**:
```typescript
globalHiddenEdges.forEach((edgeData, edgeId) => {
    // Restore if both ends exist and are visible
    if (!hiddenTypes.has(sourceType) && !hiddenTypes.has(targetType)) {
        cy.add(edgeData);
        edgesToRestore.push(edgeId);
    }
});
edgesToRestore.forEach(id => globalHiddenEdges.delete(id));
```

### Verification

| Step           | Edge Count             |
| -------------- | ---------------------- |
| Initial        | 499                    |
| Hide CVE + CWE | 495 (includes bridges) |
| Show CVE + CWE | **499** ✓              |

No edges lost!

---

## 3. Dynamic Graph Stats

**Feature**: Settings modal now shows **live** node/edge counts reflecting current visible state.

### Implementation

Added `updateLiveStats()` in `sidebar.ts`:

```typescript
export function updateLiveStats(): void {
    const cy = getCy();
    const visibleNodes = cy.nodes().filter(n => !n.hasClass('exploit-hidden')).length;
    const visibleEdges = cy.edges().filter(e => !e.hasClass('exploit-hidden')).length;
    // Update DOM
}
```

Called in `openSettings()` in `modal.ts`.

### Behavior

Stats dynamically reflect:
- **Visibility toggles** - hidden nodes removed from count
- **Exploit Paths filter** - only exploit path elements counted
- **Singularity sliders** - count updates after rebuild

---

## Files Modified

| File                              | Changes                                     |
| --------------------------------- | ------------------------------------------- |
| `frontend/js/features/filter.ts`  | `computeBridgeColor()`, global edge storage |
| `frontend/js/config/constants.ts` | Dynamic bridge edge colors in style         |
| `frontend/js/ui/sidebar.ts`       | `updateLiveStats()` function                |
| `frontend/js/ui/modal.ts`         | Call `updateLiveStats()` on open            |

---

## Commits

| Commit    | Description                                         |
| --------- | --------------------------------------------------- |
| `2d340a6` | feat: Color bridge edges based on hidden edge types |
| `ca2c7fb` | fix: Edge restoration on visibility toggle          |
| `ad5ccdd` | feat: Dynamic graph stats in Settings modal         |

---

## Testing Notes

- Edge restoration verified: 499 → 499 after full hide/show cycle
- Bridge colors vary based on edge types being hidden
- Stats update when opening Settings after toggling visibility
