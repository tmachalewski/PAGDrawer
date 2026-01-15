# Reachability Filtering Feature

**Date:** 2026-01-11

## Overview

Added reachability filtering to dim hosts that the ATTACKER cannot directly reach via `CAN_REACH` edges.

## Changes

### Frontend JS Modules

- **`environment.js`** - Added `applyReachabilityFilter()` and `dimHostAndDownstream()` functions
- **`filter.js`** - Modified to preserve unreachable styling during type filtering (uses `faded-unreachable` class)
- **`constants.js`** - Added `.unreachable` and `.faded-unreachable` Cytoscape styles
- **`main.js`** - Exposed `window.cy` for testing

### Visual Behavior

| Hosts                    | Status                              | Style                           |
| ------------------------ | ----------------------------------- | ------------------------------- |
| `host-001`, `host-002`   | Reachable (CAN_REACH from ATTACKER) | Full opacity                    |
| `host-003` to `host-006` | Unreachable                         | 30% opacity, gray dotted border |

### Filter Interaction

When applying type filters (e.g., CWE):
- Reachable nodes → `faded` class (normal fade)
- Unreachable nodes → `faded-unreachable` class (extra dimmed, 15% opacity)

## Tests Added

6 new tests in `TestReachabilityFiltering` class (`tests/test_frontend.py`):

1. `test_reachability_log_appears` - Console logs reachable hosts
2. `test_unreachable_class_applied` - Nodes have `.unreachable` class
3. `test_reachable_hosts_not_dimmed` - host-001/002 not dimmed
4. `test_unreachable_hosts_are_dimmed` - host-003-006 are dimmed
5. `test_filter_preserves_unreachable` - CWE filter preserves styling
6. `test_reset_filter_restores_unreachable` - "All" restores styling

**Total tests: 33 (all passing)**
