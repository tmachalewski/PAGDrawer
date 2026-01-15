# Node Details Hover Tooltip
**Date:** 2026-01-13 18:27

## Summary
Moved Node Details from the sidebar panel to a hover tooltip that appears when hovering over any node in the graph.

---

## Changes

### Behavior
| Before                                      | After                                       |
| ------------------------------------------- | ------------------------------------------- |
| Click node → details shown in sidebar panel | Hover node → details shown in tooltip       |
| Tooltip only for dimmed nodes (warning)     | Tooltip for ALL nodes + warnings for dimmed |

### UX Flow
1. **Hover any node** → Tooltip shows id, type, label, and other properties
2. **Hover dimmed node** → Tooltip shows details + warning section explaining why grayed out
3. **Mouse out** → Tooltip disappears
4. **Click node** → Highlights connected neighbors (preserved behavior)

---

## Files Modified

| File                          | Change                                                      |
| ----------------------------- | ----------------------------------------------------------- |
| `frontend/js/ui/tooltip.ts`   | Rewrote to show details for all nodes + warnings for dimmed |
| `frontend/js/graph/events.ts` | Removed sidebar updates, click only highlights neighbors    |
| `frontend/index.html`         | Removed Node Details section from sidebar                   |
| `frontend/css/styles.css`     | Added tooltip detail classes, warning section styles        |
| `tests/test_frontend.py`      | Updated TestNodeSelection with tooltip tests                |

---

## New CSS Classes
- `.tooltip-details` - Container for node properties
- `.tooltip-detail-row` - Single property row
- `.tooltip-detail-key` / `.tooltip-detail-value` - Key/value styling
- `.tooltip-warning` - Warning section with visual separator

---

## Test Results
All 37 Playwright tests pass:
```
tests/test_frontend.py - 37 passed in 76.98s
```

New tests added:
- `test_tooltip_element_exists`
- `test_hover_shows_tooltip`
- `test_node_click_highlights_neighbors`
