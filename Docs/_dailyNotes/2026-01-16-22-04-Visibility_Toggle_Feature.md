# Visibility Toggle Feature

**Date:** 2026-01-16
**Status:** Completed

---

## Summary

Added visibility toggle buttons to the Node Types filter panel allowing users to hide/show nodes of specific types. When nodes are hidden, bridge edges (cyan dashed lines) are created to maintain graph connectivity between predecessors and successors.

---

## Background

Users needed the ability to temporarily hide certain node types from the graph view to focus on specific parts of the attack chain without losing the context of connections. The existing "Hide Selected" feature worked on individual node selection, but there was no way to hide all nodes of a given type at once.

---

## New Feature: Visibility Toggles

### UI Changes (`frontend/index.html`)

Each node type in the filter panel now has a visibility toggle button (👁) to the right of the filter button:

```html
<div class="node-type-row">
    <button class="filter-btn legend-filter-btn" data-type="CVE">
        <div class="legend-dot" style="background: #eab308;"></div>
        <span>CVE</span>
    </button>
    <button class="visibility-toggle" data-type="CVE" title="Hide/Show CVE nodes">👁</button>
</div>
```

### Styling (`frontend/css/styles.css`)

- `.node-type-row` - flex container aligning filter button and toggle
- `.visibility-toggle` - styled button that dims when the type is hidden
- `.visibility-toggle.hidden` - reduced opacity state indicating nodes are hidden

### Core Logic (`frontend/js/features/filter.ts`)

**New Functions:**
- `toggleTypeVisibility(type)` - main entry point, toggles hide/show
- `hideNodeType(type)` - removes nodes of given type, creates bridge edges
- `showNodeType(type)` - restores nodes and original edges, removes bridge edges
- `resetVisibility()` - restores all hidden types (called by "Restore All")
- `reapplyHiddenTypes()` - re-hides types after graph rebuild (settings save)

**State Management:**
```typescript
const hiddenTypes: Set<string> = new Set();
const hiddenByType: Map<string, HiddenTypeData> = new Map();
const typeBridgeEdges: Map<string, EdgeSingular[]> = new Map();
```

**Bridge Edge Creation:**
When hiding a node type, bridge edges are created connecting each predecessor to each successor, maintaining visual connectivity:
```typescript
const bridgeEdge = cy.add({
    group: 'edges',
    data: {
        id: `bridge_${pred.id()}_${succ.id()}_${type}`,
        source: pred.id(),
        target: succ.id(),
        type: 'BRIDGE',
        isBridge: true
    }
});
```

Bridge edges are styled as cyan dashed lines (same as Hide Selected feature).

---

## Bug Fixes

### 1. Edge Loss on Multi-Type Restore

**Problem:** When hiding multiple types and using "Restore All", edges between restored types were lost (e.g., 133 edges → 87 edges).

**Cause:** Sequential restoration checked `hiddenTypes` set during edge restoration, but other types were still in the set, causing edges between types to be filtered out.

**Solution:** Two-pass restoration in `resetVisibility()`:
1. Pass 1: Restore all nodes from all hidden types
2. Clear `hiddenTypes` set
3. Pass 2: Restore all edges from all hidden types

### 2. Hidden Types Lost After Settings Save

**Problem:** Changing granularity settings caused hidden nodes to reappear.

**Cause:** Graph rebuild destroys all nodes, but `hiddenTypes` state remained in memory without being reapplied.

**Solution:** Added `reapplyHiddenTypes()` function called in `saveSettings()` after graph rebuild:
```typescript
// In modal.ts saveSettings()
destroyCytoscape();
initCytoscape(graphData.elements);
setupEventHandlers();
reapplyHiddenTypes();  // Preserve hidden types
```

---

## Integration Points

### With Hide Selected (`frontend/js/features/hideRestore.ts`)

The "Restore All" button now also resets visibility toggles:
```typescript
export function restoreAllNodes(): void {
    // ... restore individually hidden nodes ...
    resetVisibility();  // Also reset visibility toggles
    runLayout();
}
```

### With Settings Modal (`frontend/js/ui/modal.ts`)

Hidden types are preserved across settings changes by calling `reapplyHiddenTypes()` after graph rebuild.

---

## Files Changed

```
frontend/index.html              - Added visibility toggle HTML structure
frontend/css/styles.css          - Toggle button styling
frontend/js/features/filter.ts   - Core visibility toggle logic
frontend/js/features/hideRestore.ts - Integration with Restore All
frontend/js/ui/modal.ts          - Integration with settings save
tests/test_frontend.py           - 10 new E2E tests
```

---

## Testing

Added 10 comprehensive E2E tests in `TestVisibilityToggle` class:

1. `test_visibility_toggles_exist` - Verifies UI elements exist for all node types
2. `test_single_toggle_hide_show` - Basic hide/show cycle
3. `test_toggle_same_type_multiple_times` - Rapid toggling stability
4. `test_toggle_multiple_types_then_restore` - Hide multiple types, restore all at once
5. `test_toggle_multiple_types_individually_restore` - Hide multiple types, restore one by one
6. `test_toggle_adjacent_types` - Hiding types that are directly connected by edges
7. `test_no_bridge_edges_after_full_restore` - Ensures clean state after restore
8. `test_hidden_types_preserved_after_settings_save` - Settings persistence (single type)
9. `test_multiple_hidden_types_preserved_after_settings_save` - Settings persistence (multi-type)
10. `test_visibility_toggle_with_hide_selected` - Interaction between visibility toggle and Hide Selected feature

All 177 tests pass (10 new + 167 existing).

---

## Technical Notes

### Bridge Edge Styling

Bridge edges reuse the same styling as the Hide Selected feature:
- Color: Cyan (`#00ffff`)
- Style: Dashed
- Opacity: 0.5

### State Preservation Pattern

The visibility state is stored in memory (not persisted to server):
- `hiddenTypes` - Set of currently hidden type names
- `hiddenByType` - Map storing original nodes/edges for restoration
- `typeBridgeEdges` - Map storing created bridge edges for removal

### Two-Pass Restoration Pattern

Critical for multi-type restore to avoid edge loss:
```typescript
export function resetVisibility(): void {
    const typesToShow = Array.from(hiddenTypes);

    // Pass 1: Restore all nodes first
    typesToShow.forEach(type => {
        const data = hiddenByType.get(type);
        data.nodes.forEach(nodeData => cy.add({ group: 'nodes', data: nodeData }));
    });

    // Clear state BEFORE edge restoration
    hiddenTypes.clear();

    // Pass 2: Restore all edges
    typesToShow.forEach(type => {
        const data = hiddenByType.get(type);
        data.edges.forEach(edgeData => {
            if (cy.getElementById(edgeData.source).length &&
                cy.getElementById(edgeData.target).length) {
                cy.add({ group: 'edges', data: edgeData });
            }
        });
    });
}
```
