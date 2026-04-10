# 2026-04-10 - Chain-Depth-Aware Multi-Stage Attack Wiring

## Overview

Major refactor of the graph builder to use BFS (breadth-first search) for assigning chain depths to CVE/CWE/TI/VC nodes. This fixes the ENABLES edge self-loop bug and enables correct multi-stage attack chain visualization.

---

## Problem

PR:H was not creating an ENABLES edge to CVE-2022-2588 (which requires PR:L), even though PR:H >= PR:L in the VC hierarchy.

**Root cause:** When multiple CVEs produce the same VC node (e.g., both CVE-2024-4741 and CVE-2022-2588 produce PR:H via CWE-416), the self-loop check in `_wire_multistage_attacks()` blocked ALL ENABLES edges from that VC to ANY of its producer CVEs. This was overly conservative — PR:H from CVE-2024-4741 should validly enable CVE-2022-2588.

## Solution

Replaced single-pass `_wire_multistage_attacks()` with iterative BFS that assigns chain depths:

- **Depth 0**: CVEs directly exploitable by attacker's initial capabilities (AV:N, PR:N)
- **Depth N**: CVEs whose AV/PR prerequisites are met by VCs gained at depth < N
- **ENABLES edges**: Only connect forward (depth N → depth N+1), eliminating self-loops by construction

### Key Changes

| File | Change |
|------|--------|
| `src/graph/builder.py` | Major refactor: split `_build_layer` into `_build_layer_infrastructure` + `_build_attack_chains_bfs`. Added `_prereqs_satisfied`, `_build_cve_chain`, `_wire_enables_for_depth`, `_collect_gained_vc_values`. Removed `_wire_multistage_attacks`. |
| `frontend/js/ui/tooltip.ts` | Added `chain_depth` → `attack step` display name mapping |
| `tests/test_builder.py` | Updated `TestMultistageAttacks` to test BFS-based wiring |

### Node ID Changes

All CVE, CWE, TI, VC nodes now include `:dN` depth suffix:

```
Before: CVE-2022-2588@cpe:2.3:a:musl:musl:...@host_webapp_...
After:  CVE-2022-2588:d1@cpe:2.3:a:musl:musl:...@host_webapp_...
                     ^^^
```

This prevents nodes at different chain depths from merging when universality sliders collapse them.

### BFS Algorithm

```
1. Build infrastructure (HOST, CPE nodes)
2. Collect CVE entries (don't create nodes yet)
3. BFS loop:
   - Find CVEs whose AV/PR prereqs are satisfied by available VCs
   - Assign chain_depth, create CVE→CWE→TI→VC nodes
   - Wire ENABLES edges from depth-N VCs to depth-(N+1) CVEs
   - Add newly gained VCs to available set
   - Repeat until no new CVEs assignable
4. Unreachable CVEs are never created (hidden)
```

### Design Decisions

- **AC/UI are graph-wide constants**, not chain participants
- **Chain depth shown in tooltip only** (as "attack step"), not in node labels
- **Unreachable CVEs hidden entirely** (not created in graph)
- **Depth applies to CVE, CWE, TI, VC** — ATTACKER/HOST/CPE don't get depth

---

## Verification

- 330 Python tests + 82 TypeScript tests = all pass
- Slider showcase scan: CVE-2022-2588 correctly at depth 1, with ENABLES edges from both VC:AV:L:d0 and VC:PR:H:d0
- Mock data: 8 depth-0 CVEs (L1), 8 depth-1 CVEs (L1), 24 ENABLES edges
