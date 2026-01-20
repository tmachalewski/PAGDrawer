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

| Commit    | Description                                             |
| --------- | ------------------------------------------------------- |
| `2d340a6` | feat: Color bridge edges based on hidden edge types     |
| `ca2c7fb` | fix: Edge restoration on visibility toggle              |
| `ad5ccdd` | feat: Dynamic graph stats in Settings modal             |
| `10516e1` | test: Add regression test for edge restoration          |
| `6d5bab0` | fix: Update tests for signature changes and stats moved |

---

## Test Fixes

After running full test suite, 8 tests failed due to code changes made:

### 1. `TestWireCweToVcs` (5 tests)

**Issue**: `_wire_cwe_to_vcs()` signature changed during VC singularity fix, adding `cpe_id` and `cve_id` params.

**Fix**: Updated all test calls to include `None` for new params:
```python
empty_graph_builder._wire_cwe_to_vcs(
    cwe_id,
    "host-001",
    None,  # cpe_id
    None,  # cve_id
    "CVSS:3.1/AV:N/...",
    impacts,
    ""
)
```

### 2. Stats Location Tests (2 tests)

**Issue**: `test_node_count_displayed` and `test_edge_count_displayed` looked for stats in `.stats-panel` but stats moved to Settings modal.

**Fix**: Updated tests to open Settings modal and check there.

### 3. Slider Test (1 test)

**Issue**: `test_slider_affects_graph_node_count` used modal text for counts, which was unreliable.

**Fix**: Use JavaScript to get counts directly from Cytoscape:
```python
initial_count = int(page.evaluate("getCy().nodes().length"))
```

---

## Regression Test Added

Added `test_edge_restoration_same_order_show` to document the edge restoration bug:

```python
def test_edge_restoration_same_order_show(self, page: Page):
    """Regression test: Edges must be preserved when showing types in SAME order as hiding."""
    # Hide CVE → Hide CWE
    # Show CVE → Show CWE (same order - was buggy)
    # Verify edge count matches initial
```

---

## Testing Summary

| Suite           | Count | Status     |
| --------------- | ----- | ---------- |
| Frontend (E2E)  | 58    | ✅ All pass |
| Builder         | 46+   | ✅ All pass |
| Full test suite | 372   | ✅ All pass |

---

## Testing Notes

- Edge restoration verified: 499 → 499 after full hide/show cycle
- Bridge colors vary based on edge types being hidden
- Stats update when opening Settings after toggling visibility
- All 58 frontend tests pass in ~2 minutes

