# Technical Impact (TI) Nodes Implementation
**Date:** 2026-01-11 16:56

## Summary
Added Technical Impact (TI) nodes as an intermediate layer between CWE and VC nodes, implementing the flow: **CVE → CWE → TI → VC**

## Changes Made

### Schema (`src/core/schema.py`)
- Added `TI = auto()` to `NodeType` enum (now 6-node schema)
- Added `HAS_IMPACT = auto()` to `EdgeType` enum (CWE → TI edge)

### Backend (`src/graph/builder.py`)
- Updated `_wire_cwe_to_vcs()` to create TI nodes between CWE and VC
- TI nodes are **singular (per-CWE)**: each CWE has its own TI node
- TI ID format: `TI:{impact}@{cwe_id}`
- Edge structure: CWE → TI (HAS_IMPACT), TI → VC (LEADS_TO)

### Configuration (`src/core/config.py`)
- Added `"TI": "singular"` to default node_modes

### Frontend (`frontend/index.html`)
- Added TI color: `#00bfff` (cyan/deep sky blue)
- Added HAS_IMPACT edge color: `#00bfff`
- Added TI to sidebar legend
- Added TI filter button
- Added TI to Node Grouping Settings modal (singular as default)
- Updated `saveSettings()` to include TI

## Graph Statistics
- **Before TI:** 143 nodes, 168 edges
- **After TI (singular):** 175 nodes, 218 edges

## Technical Impacts
The TI nodes represent CWE Common Consequences from the consensual matrix:
- Execute Unauthorized Code or Commands → AV:L, PR:H, EX:Y
- Gain Privileges or Assume Identity → AV:L, PR:H, EX:Y
- Read Memory → AV:L, PR:H
- Bypass Protection Mechanism → AV:L, PR:H
- DoS variants → No privilege gain
