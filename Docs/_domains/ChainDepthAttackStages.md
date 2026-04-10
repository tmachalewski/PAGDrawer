# Chain-Depth-Aware Multi-Stage Attack Wiring

This document describes how PAGDrawer models multi-stage attack chains using chain depth assignment via BFS (breadth-first search).

---

## Motivation

Real-world attacks are rarely single-step. An attacker might:

1. Exploit a remote vulnerability (AV:N) to gain local access (AV:L)
2. Use local access to exploit a privilege escalation CVE (AV:L/PR:L)
3. With elevated privileges, exploit further CVEs (PR:H)

PAGDrawer models this progression by assigning a **chain depth** to each attack-progression node (CVE, CWE, TI, VC). The depth represents the minimum number of exploitation steps needed to reach that node.

---

## Chain Depth Definition

| Depth | Meaning | Example |
|-------|---------|---------|
| 0 | Directly exploitable by attacker's initial capabilities | CVE with AV:N/PR:N |
| 1 | Requires one prior exploitation step | CVE with AV:L (needs AV:L gained from depth-0) |
| 2 | Requires two prior steps | CVE with PR:H (needs PR:H from depth-1) |
| N | Requires N prior steps | Determined by BFS |

### Which nodes carry depth?

| Node Type | Has Depth? | Reason |
|-----------|-----------|--------|
| ATTACKER | No | Entry point, not an attack step |
| HOST | No | Infrastructure, not attack progression |
| CPE | No | Infrastructure, not attack progression |
| **CVE** | **Yes** | Vulnerability — exploited at a specific step |
| **CWE** | **Yes** | Weakness — inherited from parent CVE's depth |
| **TI** | **Yes** | Technical impact — inherited from parent CWE's depth |
| **VC** | **Yes** | Vector changer — gained at a specific step |

---

## BFS Algorithm

The builder constructs the attack graph in BFS waves rather than a single pass. This is implemented in `_build_attack_chains_bfs()` in `src/graph/builder.py`.

### Overview

```
Phase 1: Build infrastructure (HOST, CPE nodes + edges)
Phase 2: BFS depth assignment

  Initial available VCs = {AV:N, PR:N}  (attacker's starting capabilities)

  While unprocessed CVEs remain AND depth <= max_depth:
    1. Find CVEs whose AV/PR prerequisites are satisfied by available VCs
    2. Assign chain_depth = current_depth to these CVEs
    3. Create their downstream nodes: CVE → CWE → TI → VC (all with same depth)
    4. Wire ENABLES edges from depth-(N-1) VCs to depth-N CVEs
    5. Add newly gained VC values to available set
    6. Increment depth

  Unreachable CVEs (prerequisites never satisfiable) are never created.
```

### Prerequisite Checking

Only **AV** (Attack Vector) and **PR** (Privileges Required) participate in chain progression. **AC** (Attack Complexity) and **UI** (User Interaction) are graph-wide constants — they don't change through exploitation.

Prerequisites use the VC hierarchy:
- **AV hierarchy**: N(0) < A(1) < L(2) < P(3) — gaining AV:L satisfies requirements for AV:N, AV:A, AV:L
- **PR hierarchy**: N(0) < L(1) < H(2) — gaining PR:H satisfies requirements for PR:N, PR:L, PR:H

```python
def _prereqs_satisfied(prereqs, available_vcs):
    for vc_type, required_value in prereqs:
        if vc_type not in ("AV", "PR"):
            continue  # AC/UI are constants, skip
        required_level = HIERARCHY[vc_type][required_value]
        satisfied = any(
            HIERARCHY[vc_type][v] >= required_level
            for t, v in available_vcs if t == vc_type
        )
        if not satisfied:
            return False
    return True
```

### ENABLES Edge Wiring

ENABLES edges connect VCs at depth N to CVEs at depth N+1:

```
VC:AV:L:d0  ──ENABLES──→  CVE-2022-2588:d1
VC:PR:H:d0  ──ENABLES──→  CVE-2022-2588:d1
```

**No self-loop check is needed.** Because ENABLES edges only go forward in depth (N → N+1), cycles are impossible by construction. This eliminates the previous bug where merged VC nodes incorrectly blocked valid ENABLES edges.

The wiring also respects the host context from universality sliders:
- When VC is per-host: VCs on host-A only enable CVEs on host-A
- When VC is universal: VCs enable CVEs on all hosts

---

## Node ID Format

Chain depth is encoded in node IDs as a `:dN` suffix, placed before the context separator (`@` or layer suffix):

### ID Patterns by Grouping Level

| Node | Universal | Per-Host | Per-Parent |
|------|----------|----------|------------|
| CVE | `CVE-2022-2588:d1` | `CVE-2022-2588:d1@host-01` | `CVE-2022-2588:d1@cpe:...@host-01` |
| CWE | `CWE-416:d0` | `CWE-416:d0@host-01` | `CWE-416:d0@CVE-2022-2588:d1@...` |
| TI | `TI:Execute Code:d0` | `TI:Execute Code:d0@host-01` | `TI:Execute Code:d0@CWE-416:d0@...` |
| VC | `VC:PR:H:d0` | `VC:PR:H:d0@host-01` | `VC:PR:H:d0@TI:Execute Code:d0@...` |

### Why depth is in the ID

Depth in the ID prevents incorrect merging when universality sliders collapse nodes. Without it:
- A universal `VC:PR:H` node would merge PR:H gained at depth 0 with PR:H gained at depth 1
- The merged node's producer set would include CVEs from both depths
- Self-loop checks would block valid ENABLES edges

With depth in the ID:
- `VC:PR:H:d0` and `VC:PR:H:d1` are separate nodes at all slider positions
- Each node cleanly represents capabilities gained at a specific attack stage
- ENABLES edges only go forward (d0 → d1), never backward

---

## Layer Interaction

The 2-layer model (L1 external, L2 internal) interacts with chain depth:

### Layer 1 (External Attack Surface)
- **Initial VCs**: {AV:N, PR:N} (attacker's starting capabilities)
- BFS assigns depths starting at 0
- Typical pattern: depth-0 = remote CVEs, depth-1 = local privilege escalation

### Bridge (INSIDE_NETWORK)
- L1 EX:Y (exploited) nodes connect to L2 hosts via bridge
- This represents network perimeter breach

### Layer 2 (Internal Network)
- **Initial VCs**: All VCs gained in L1 + AV:A (adjacent access from being inside)
- BFS assigns depths starting at 0 (within L2)
- Most L2 CVEs are depth 0 since the attacker has extensive capabilities from L1

---

## Example: Slider Showcase Scan

The `examples/slider_showcase_trivy_scan.json` demonstrates a 2-step attack chain:

### Depth 0 (Directly Exploitable)

| CVE | CVSS | Prereqs | Why Depth 0 |
|-----|------|---------|-------------|
| CVE-2024-4741 | AV:N/AC:L/PR:N/UI:N | AV:N, PR:N | Attacker has both |
| CVE-2024-5535 | AV:N/AC:L/PR:N/UI:N | AV:N, PR:N | Attacker has both |
| CVE-2024-3596 | AV:N/AC:H/PR:N/UI:N | AV:N, PR:N | Attacker has both (AC is a constant) |
| CVE-2024-6119 | AV:N/AC:L/PR:N/UI:N | AV:N, PR:N | Attacker has both |
| CVE-2024-2961 | AV:N/AC:L/PR:N/UI:N | AV:N, PR:N | Attacker has both |
| CVE-2023-44487 | AV:N/AC:L/PR:N/UI:N | AV:N, PR:N | Attacker has both |

**VCs gained at depth 0**: AV:L, PR:H, EX:Y (from CWE-416, CWE-125, CWE-22, CWE-287, etc.)

### Depth 1 (Requires Prior Exploitation)

| CVE | CVSS | Prereqs | Why Depth 1 |
|-----|------|---------|-------------|
| CVE-2022-2588 | AV:L/AC:L/PR:L/UI:N | AV:L, PR:L | AV:L gained from depth 0; PR:L satisfied by PR:H (hierarchy: H >= L) |

**ENABLES edges created**:
```
VC:AV:L:d0  ──ENABLES──→  CVE-2022-2588:d1  (AV:L satisfies AV:L requirement)
VC:PR:H:d0  ──ENABLES──→  CVE-2022-2588:d1  (PR:H satisfies PR:L requirement via hierarchy)
```

### Attack Chain Visualization

```
ATTACKER ─→ HOST ─→ CPE ─→ CVE-2024-4741:d0 ─→ CWE-416:d0 ─→ TI:d0 ─→ VC:AV:L:d0
                                                                          VC:PR:H:d0
                                                                             │  │
                                                              ENABLES ───────┘  │
                                                              ENABLES ──────────┘
                                                                             │
                                                                             v
                                              CVE-2022-2588:d1 ─→ CWE-416:d1 ─→ TI:d1 ─→ VC:PR:H:d1
                                                                                          VC:EX:Y:d1
```

---

## Unreachable CVEs

CVEs whose prerequisites can never be satisfied are not created in the graph. This happens when:
- A CVE requires AV:P (physical access) but no chain produces AV:P
- A CVE requires PR:H but no chain produces PR:L or PR:H

These CVEs are simply absent from the graph — they represent attacks that cannot occur given the current vulnerability landscape.

This is distinct from **environment-filtered** CVEs (AC:H or UI:R), which are still created but visually dimmed with a red dashed border. Environment filtering is a separate mechanism from chain depth.

---

## Tooltip Display

Chain depth appears in node tooltips as **"attack step"**:

```
id: CVE-2022-2588:d1@cpe:2.3:a:musl:musl:...
label: CVE-2022-2588
attack step: 1
cvss_vector: CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H
...
```

Chain depth is NOT shown in node labels to avoid visual clutter.

---

## Configuration

| Setting | Value | Rationale |
|---------|-------|-----------|
| Max depth | 10 | Prevents infinite loops in pathological cases |
| AC/UI participation | None (constants) | AC and UI don't change through exploitation |
| Initial VCs (L1) | AV:N, PR:N | Attacker starts with network access, no privileges |
| Initial VCs (L2) | All L1 VCs + AV:A | Post-breach, attacker has everything from L1 plus adjacent access |

---

## Implementation Details

### Key Methods in `src/graph/builder.py`

| Method | Purpose |
|--------|---------|
| `_build_layer_infrastructure()` | Creates HOST, CPE nodes; collects CVE entries for BFS |
| `_build_attack_chains_bfs()` | BFS loop: assigns depths, builds chains, wires ENABLES |
| `_prereqs_satisfied()` | Checks if AV/PR prereqs are met by available VCs (with hierarchy) |
| `_build_cve_chain()` | Creates CVE → CWE → TI → VC nodes at a given depth |
| `_wire_enables_for_depth()` | Creates ENABLES edges from depth-N VCs to depth-(N+1) CVEs |
| `_collect_gained_vc_values()` | Collects (vc_type, vc_value) pairs from a layer's VC nodes |
| `_wire_cwe_to_vcs()` | Creates TI → VC chain with depth suffix in IDs |

### Data Flow

```
load_from_data() / load_from_mock_data()
  │
  ├─ _build_layer_infrastructure("")          → HOST/CPE nodes, CVE entries list
  ├─ _add_attacker_node()                     → ATTACKER + initial VCs
  ├─ _build_attack_chains_bfs(entries, ...)   → BFS: CVE/CWE/TI/VC + ENABLES
  │     ├─ _prereqs_satisfied()               → depth assignment
  │     ├─ _build_cve_chain()                 → node creation
  │     │     └─ _wire_cwe_to_vcs()           → TI/VC chain
  │     └─ _wire_enables_for_depth()          → ENABLES edges
  │
  ├─ _build_layer_infrastructure(":IN")       → L2 HOST/CPE
  ├─ _create_inside_network_bridge()          → L1 EX:Y → BRIDGE → L2 hosts
  └─ _build_attack_chains_bfs(entries, ...)   → L2 BFS
```
