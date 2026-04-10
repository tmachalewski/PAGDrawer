# Plan: Chain-Depth-Aware Multi-Stage Attacks

**Date:** 2026-04-10
**Status:** Draft

---

## Problem Statement

### The Bug (Immediate)

PR:H does not create an ENABLES edge to CVE-2022-2588 (which requires PR:L), even though PR:H >= PR:L in the VC hierarchy.

**Root cause:** The self-loop prevention in `_wire_multistage_attacks()` is overly conservative when VC nodes are shared/merged. The code traces backwards from each VC node to find all producer CVEs, then blocks ENABLES edges to any CVE that appears in that producer set:

```python
# Current logic (builder.py ~line 700)
for vc_node_id in satisfying_vcs:
    producer_cves = vc_producer_cves.get(vc_node_id, set())
    if cve["id"] in producer_cves:  # ← blocks if target CVE is ANY producer
        continue
```

When two CVEs (e.g., CVE-2024-4741 and CVE-2022-2588) both produce PR:H via the same CWE-416, they share a single merged PR:H node. That node's `producer_cves = {CVE-2024-4741, CVE-2022-2588}`. The self-loop check then prevents PR:H from enabling EITHER CVE, even though PR:H from CVE-2024-4741 is a perfectly valid enabler for CVE-2022-2588.

### The Design Problem (Broader)

A CVE can appear at different positions in different attack chains:
- **Chain A:** ATTACKER → CVE-X (step 1) → VC:AV:L → CVE-Y (step 2) → VC:PR:H → CVE-Z (step 3)
- **Chain B:** ATTACKER → CVE-Y (step 1, if directly reachable)

When TI/VC nodes merge via universality sliders, we lose chain-depth information. A TI produced at step 1 and a TI produced at step 2 collapse into one node, making it impossible to distinguish attack progression stages.

This matters for:
1. **Correct ENABLES wiring** — VCs from step N should enable CVEs at step N+1, not loop back
2. **Visual analysis** — users need to see which TIs/VCs came from which exploitation stage
3. **Slider merging** — merging should only collapse nodes within the same chain depth

---

## Proposed Solution: Chain-Depth-Aware VC/TI Nodes

### Core Concept

Assign a **chain depth** (integer) to each CVE, CWE, TI, and VC node. Chain depth represents the minimum number of exploitation steps needed to reach that node:

```
Depth 0: CVEs directly exploitable by attacker's initial capabilities (AV:N, PR:N, UI:N, AC:L)
Depth 1: CVEs enabled by VCs from depth-0 exploits
Depth 2: CVEs enabled by VCs from depth-1 exploits
...
```

### Algorithm: Iterative BFS Wiring

Replace the current single-pass `_wire_multistage_attacks()` with an iterative BFS approach:

```
1. Identify depth-0 CVEs:
   - Extract prerequisites from each CVE's CVSS vector
   - A CVE is depth-0 if ALL its prerequisites are satisfied by
     the attacker's initial VCs (AV:N, PR:N, UI:N, AC:L)
   - Tag these CVEs with chain_depth=0

2. Tag downstream nodes:
   - All CWE, TI, VC nodes produced by depth-0 CVEs get chain_depth=0

3. Iterate (depth = 1, 2, 3, ...):
   a. Collect all VCs at depth (depth-1)
   b. For each unassigned CVE, check if its prerequisites are satisfied
      by any VC at depth <= (depth-1), using hierarchy rules
   c. Newly satisfied CVEs get chain_depth=depth
   d. Tag their downstream CWE/TI/VC nodes with chain_depth=depth
   e. Create ENABLES edges: VC@depth(N-1) → CVE@depth(N)
   f. Stop when no new CVEs are assigned

4. Any CVEs never assigned a depth are unreachable
   (prerequisites cannot be satisfied by any chain)
```

### Node ID Changes

Include chain depth in node IDs to prevent incorrect merging:

```
Current:  VC:PR:H@host-web-01     (or VC:PR:H at universal level)
Proposed: VC:PR:H:d0@host-web-01  (or VC:PR:H:d0 at universal level)
```

This means PR:H from a depth-0 exploit and PR:H from a depth-1 exploit are separate nodes, even when sliders merge them to universal level. The slider merging still works within each depth.

**Affected ID patterns:**
| Node Type | Current ID | Proposed ID |
|-----------|-----------|-------------|
| CVE (always per-CPE) | `CVE-2022-2588@cpe:...` | `CVE-2022-2588:d1@cpe:...` |
| CWE (universal) | `CWE-416` | `CWE-416:d0` |
| CWE (per-CVE) | `CWE-416@CVE-2022-2588` | `CWE-416:d1@CVE-2022-2588` |
| TI (universal) | `TI:Execute_Code` | `TI:Execute_Code:d0` |
| TI (per-host) | `TI:Execute_Code@host-01` | `TI:Execute_Code:d0@host-01` |
| VC (universal) | `VC:PR:H` | `VC:PR:H:d0` |
| VC (per-host) | `VC:PR:H@host-01` | `VC:PR:H:d0@host-01` |
| VC (per-TI) | `VC:PR:H@TI_xyz` | `VC:PR:H:d0@TI_xyz` |

All four node types (CVE, CWE, TI, VC) carry chain depth. ATTACKER, HOST, and CPE nodes do NOT get depth — they are infrastructure nodes, not attack-progression nodes.

### ENABLES Edge Logic (Simplified)

With chain depth, self-loop prevention becomes trivial — no backward tracing needed:

```python
# New logic:
# ENABLES edges only go forward: VC@depth(N) → CVE@depth(N+1)
# No self-loop check needed — depth ordering guarantees acyclicity
for vc_node in vc_nodes_at_depth[depth]:
    for cve in unresolved_cves:
        if vc_satisfies_prerequisite(vc_node, cve):
            create_enables_edge(vc_node, cve)
            cve.chain_depth = depth + 1
```

---

## Impact Analysis

### Files to Modify

| File | Change |
|------|--------|
| `src/graph/builder.py` | Major refactor: iterative BFS in `_wire_multistage_attacks()`, chain_depth param in `_wire_cve_to_cwe()`, `_wire_cwe_to_tis()`, `_wire_cwe_to_vcs()` for ID generation. Hide unreachable CVEs (and their downstream). |
| `src/core/config.py` | No change expected (slider logic unchanged, just new ID suffix) |
| `src/core/schema.py` | Add `chain_depth` to node attribute documentation |
| `frontend/js/ui/sidebar.ts` | No change (counts by type, depth is transparent) |
| `frontend/js/ui/tooltip.ts` | Show chain_depth in tooltip for CVE, CWE, TI, VC nodes |
| `tests/test_builder.py` | Update ID assertions, add chain-depth-specific tests |

### Edge Cases to Handle

1. **CVE reachable at multiple depths**: A CVE might be exploitable at depth 0 (directly) AND depth 2 (via chain). Use minimum depth? Create nodes at both depths? → **Recommendation: use minimum depth** (first opportunity to exploit).

2. **Circular chains**: CVE-A enables CVE-B enables CVE-A. The BFS approach naturally prevents this — once a CVE is assigned a depth, it's not reconsidered.

3. **VC hierarchy across depths**: Should VC:PR:H@d0 enable a CVE requiring PR:L at depth 1? → **Yes**, the hierarchy still applies, but only VCs from depth < target_depth can enable.

4. **Initial attacker VCs**: AV:N, PR:N, UI:N, AC:L are at depth -1 (or "initial"). They enable depth-0 CVEs but are NOT produced by any CVE.

5. **Universal slider edge case**: At universal level, `VC:PR:H:d0` and `VC:PR:H:d1` remain separate. This is intentional — it shows the attacker gaining PR:H capability at two different stages. If user finds this too granular, a future "collapse depths" toggle could merge them.

6. **Unreachable CVEs**: CVEs whose prerequisites can never be satisfied (e.g., requires AV:P but no chain produces AV:P) should be visually distinguished (dimmed? different border?).

---

## Example Walkthrough

Given the slider showcase scan with CVE-2022-2588 (AV:L/PR:L, CWE-416):

### Step 1: Identify depth-0 CVEs
```
Attacker initial VCs: AV:N, PR:N, UI:N, AC:L

CVE-2024-5535 (AV:N/AC:L/PR:N/UI:N) → depth 0 ✓ (all prereqs met)
CVE-2024-4741 (AV:N/AC:L/PR:N/UI:N) → depth 0 ✓
CVE-2024-3596 (AV:N/AC:H/PR:N/UI:N) → depth 0 ✓ (AC:H needs AC:L? see note*)
CVE-2024-2961 (AV:N/AC:L/PR:N/UI:N) → depth 0 ✓
CVE-2024-6119 (AV:N/AC:L/PR:N/UI:N) → depth 0 ✓
CVE-2022-2588 (AV:L/AC:L/PR:L/UI:N) → NOT depth 0 ✗ (needs AV:L, PR:L)
```

*Note: AC and UI are graph-wide constants (decided), not chain participants. CVE-2024-3596 with AC:H is handled by the existing environment filter — if the graph's AC filter is set to "Low only", this CVE would be dimmed. It does NOT affect chain depth assignment. For depth purposes, only AV and PR prerequisites matter.*

### Step 2: Process depth-0 CVEs
```
CVE-2024-5535 → CWE-416 → TI("Execute Code"):d0 → VC:AV:L:d0, VC:PR:H:d0, VC:EX:Y:d0
CVE-2024-4741 → CWE-416 → TI("Execute Code"):d0 → VC:AV:L:d0, VC:PR:H:d0, VC:EX:Y:d0
...
```

### Step 3: Depth-1 wiring
```
Available VCs: AV:L:d0, PR:H:d0 (plus initial AV:N, PR:N, UI:N, AC:L)

CVE-2022-2588 requires: AV:L (satisfied by AV:L:d0 ✓), PR:L (satisfied by PR:H:d0 via hierarchy ✓)
→ CVE-2022-2588 assigned depth 1
→ ENABLES edges: VC:AV:L:d0 → CVE-2022-2588, VC:PR:H:d0 → CVE-2022-2588
```

### Result
```
ATTACKER → [initial VCs] → depth-0 CVEs → VC:AV:L:d0, VC:PR:H:d0
                                              ↓ ENABLES      ↓ ENABLES
                                           CVE-2022-2588 (depth 1)
                                              ↓
                                           VC:PR:H:d1, VC:EX:Y:d1
```

PR:H now correctly enables CVE-2022-2588. The self-loop problem vanishes because ENABLES edges only go from depth N to depth N+1.

---

## Implementation Order

1. **Refactor builder graph construction** — Currently the builder creates all CVE→CWE→TI→VC nodes in one pass, then wires ENABLES edges after. New approach: build in BFS waves.
   - Wave 0: Create depth-0 CVE/CWE/TI/VC nodes (directly exploitable CVEs)
   - Wave N: Wire ENABLES edges from depth N-1 VCs, create depth-N CVE/CWE/TI/VC nodes
   - After all waves: hide/remove unreachable CVEs and their CPE→CVE subgraphs
2. **Update node ID generation** — include `:dN` suffix in CVE, CWE, TI, VC IDs
3. **Update initial attacker VCs** — treat as depth -1 or "initial" (pre-depth-0); AC/UI remain graph-wide constants, not depth participants
4. **Update tests** — new assertions for chain depth, updated IDs
5. **Frontend tooltip** — show chain depth in CVE, CWE, TI, VC node tooltips

---

## Decisions

1. **AC/UI in chain depth**: AC and UI are **constants for the entire graph** — they do not participate in chain progression. They remain static environmental filters applied globally. The attacker's initial UI:N and AC:L values are graph-wide properties, not per-chain capabilities.

2. **Depth in node label**: Tooltip only. No visual label clutter.

3. **Maximum chain depth**: max_depth=10 default with early termination when no new CVEs are assigned.

4. **Unreachable CVE visualization**: CVEs failing AC/UI filters are already grayed out with red dashed border (existing feature). CVEs unreachable due to missing AV/PR prerequisites (no chain produces the needed VC) should be **hidden entirely** — they represent attacks that cannot occur given the current graph state.

5. **Depth applies to CVE, CWE, TI, VC**: All four attack-progression node types carry chain depth. ATTACKER, HOST, CPE are infrastructure and do not get depth.
