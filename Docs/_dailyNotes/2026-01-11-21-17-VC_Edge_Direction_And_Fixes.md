# Session Changes - Evening Update
**Date:** 2026-01-11 21:17

## Summary
Additional fixes and improvements made to the attack graph visualization.

## Changes Made

### 1. VC Edge Direction Reversed
VCs in the Initial State box now point **TO** the ATTACKER instead of **FROM** the ATTACKER.
- **Backend** (`builder.py`): Changed `ATTACKER → VC` to `VC → ATTACKER`
- **Frontend** (`index.html`): Updated dynamic UI/AC nodes to also point TO attacker
- **Rationale**: Represents that these capabilities "lead to" the attacker's initial state

### 2. Exploit Paths Fix
Fixed ATTACKER_BOX compound node disappearing when clicking "Exploit Paths" button.
- Added code to always include ATTACKER_BOX and its children in the exploit path set
- Ensures the hacker icon and initial VCs remain visible during path highlighting

### 3. TI Singular Mode Implementation
TI nodes are now truly singular (per-CWE):
- TI ID format changed from `TI:{impact}@{host_id}` to `TI:{impact}@{cwe_id}`
- Each CWE node now has its own TI node, even if same technical impact
- Added `cwe_id` attribute to TI nodes

### 4. TI Added to Settings Modal
TI (Technical Impact) now appears in Node Grouping Settings:
- Added setting row between CWE and VC
- Default: Singular (Per-CWE)
- Updated `saveSettings()` and `config.py` to include TI

## Current Graph Statistics
- **Total Nodes:** 175
- **Total Edges:** 218
- **Node Breakdown:**
  - HOST: 12, CPE: 30, CVE: 32, CWE: 32
  - TI: 32, VC: 34, COMPOUND: 1, ATTACKER: 1, BRIDGE: 1
