# 2026-01-11 Environment Settings & Layout Changes

## Summary
Added environment-specific CVE filtering, dynamic environment VCs in the attacker box, and simplified layout options.

## Changes Made

### 1. Environment Settings Panel
Added a new panel in the sidebar to filter CVEs based on environment conditions:

- **User Interaction (UI)**:
  - `None (UI:N)` - Environment has no user interaction available
  - `Required (UI:R)` - Environment allows user interaction

- **Attack Complexity (AC)**:
  - `Low (AC:L)` - Only low-complexity attacks possible
  - `High (AC:H)` - High-complexity attacks possible

**Behavior**: CVEs that require conditions not met by the environment are faded out (25% opacity with dashed red border).

### 2. Dynamic Environment VCs in Attacker Box
The ATTACKER_BOX compound node now contains 4 VC nodes:
- **AV:N** - Network access (static, from backend)
- **PR:N** - No privileges (static, from backend)
- **UI:N/R** - User interaction environment (dynamic, from dropdown)
- **AC:L/H** - Attack complexity environment (dynamic, from dropdown)

When the user changes the environment dropdowns, the UI and AC nodes update in real-time to reflect the selected values.

### 3. Layout Simplification
- **Removed**: "Columns (by type)" layout option
- **Default**: Changed default layout to **Dagre (DAG)**
- Remaining layouts: Dagre (DAG), Breadthfirst, Force-directed, Circle

## Files Modified
- `frontend/index.html`:
  - Added Environment Settings panel HTML
  - Added `applyEnvironmentFilter()` function
  - Added `updateEnvironmentVCs()` function for dynamic VC nodes
  - Removed Columns layout, made Dagre default
  - Fixed edge styling for dynamic env VCs (`type: 'HAS_STATE'`)

## Bug Fixes
1. **Environment filter not working**: Dropdown used `filter-btn` class triggering type filter; fixed by using `env-select` class
2. **CVE selector wrong attribute**: Changed from `node_type` to `type`
3. **Edge styling mismatch**: Added `type: 'HAS_STATE'` to dynamic edges for consistent arrow styling
