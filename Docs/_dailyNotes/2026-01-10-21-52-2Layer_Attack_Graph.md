# PAGDrawer Session Notes - 2026-01-10-21-52

## Summary

Implemented 2-layer attack graph model to realistically represent network penetration phases.

## Changes Made

### 1. 2-Layer Attack Model

**Layer 1 (External)**:
- Initial attack from outside network
- Uses AV:N (network) vulnerabilities
- CAN_REACH edges for network topology

**INSIDE_NETWORK Bridge**:
- Central node representing successful perimeter breach
- All Layer 1 EX:Y nodes connect to it via ENTERS_NETWORK edges
- Connects to ALL Layer 2 hosts (full mesh)

**Layer 2 (Internal)**:
- Post-compromise attack surface
- All nodes duplicated with `:INSIDE_NETWORK` suffix
- Full mesh connectivity (no CAN_REACH restrictions)
- Can exploit AV:A (adjacent) vulnerabilities

### 2. Graph Statistics

| Metric               | Value             |
| -------------------- | ----------------- |
| Total Nodes          | 140               |
| Total Edges          | 184               |
| Hosts                | 12 (6 per layer)  |
| VCs                  | 32 (16 per layer) |
| ENTERS_NETWORK edges | 6                 |

### 3. Files Modified

- `src/graph/builder.py` - Added `_build_layer()` and `_create_inside_network_bridge()` methods
- `frontend/index.html` - Added BRIDGE node styling (green diamond) and ENTERS_NETWORK edge color

## Design Notes

- Third compromise doesn't change situation (already have AV:A to all hosts)
- Full mesh in Layer 2 (documented as simplification)
- Layer attribute on all nodes for filtering
