# Reachability Filter Fix & Tests
**Date:** 2026-01-13 12:34

## Summary
Fixed a bug where downstream nodes of unreachable hosts (like host-005) were not being correctly dimmed in the graph visualization.

---

## Problem
When host-005 had CVE nodes with multiple predecessors (e.g., a CPE node AND a VC:AV:L node), the BFS algorithm had a race condition:
- CVE was visited via CPE before VC:AV:L was marked unreachable
- CVE incorrectly thought it had a reachable predecessor
- CVE was never re-evaluated after VC:AV:L became unreachable

## Root Cause
The original algorithm used backward unreachability propagation starting from unreachable hosts. This approach failed for nodes with multiple incoming edges.

---

## Fix Applied

### `frontend/js/features/environment.ts`
Changed from backward propagation to **forward reachability propagation**:

| Before                                                 | After                                                                  |
| ------------------------------------------------------ | ---------------------------------------------------------------------- |
| Start from unreachable hosts, BFS to mark descendants  | Start from ATTACKER + reachable hosts, BFS to find all reachable nodes |
| Check if predecessors are unreachable (race condition) | Mark everything NOT in reachable set as unreachable                    |

### Algorithm (New)
1. Add ATTACKER, reachable L1 hosts, L2 hosts, and ATTACKER_BOX to reachable set
2. BFS from these starting nodes to find all reachable successors
3. Mark all nodes NOT in the reachable set as `unreachable`

---

## Tests Added

### `tests/test_frontend.py` - TestReachabilityFiltering

| Test                                                  | Purpose                                                                 |
| ----------------------------------------------------- | ----------------------------------------------------------------------- |
| `test_downstream_cves_of_unreachable_host_are_dimmed` | CVEs downstream of L1 host-005 are unreachable                          |
| `test_multi_predecessor_nodes_correctly_marked`       | CVEs with multiple predecessors are unreachable if all predecessors are |
| `test_l2_hosts_remain_reachable`                      | L2 hosts via INSIDE_NETWORK bridge stay reachable                       |

### Test Results
All 9 reachability tests pass:
```
tests/test_frontend.py::TestReachabilityFiltering - 9 passed in 34.64s
```

---

## Key Insight
L2 hosts (`host-XXX:INSIDE_NETWORK`) are correctly reachable because they're accessed via the INSIDE_NETWORK bridge from jump hosts (host-001, host-002). Their CVEs should NOT be dimmed even if the L1 version of the same host is unreachable.

---

## Files Modified
- `frontend/js/features/environment.ts` - Rewrote `applyReachabilityFilter()`
- `tests/test_frontend.py` - Added 3 new tests
