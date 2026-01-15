# PAGDrawer - Project State Overview
**Date:** 2026-01-11 21:30

## Project Summary
**PAGDrawer** (Predictive Attack Graph Drawer) is a visualization tool for security attack graphs. It models how vulnerabilities on a network can be exploited to gain privileges and move laterally through systems.

## Architecture

### Backend (Python/FastAPI)
- **Framework**: FastAPI + Uvicorn
- **Graph Library**: NetworkX
- **Entry Point**: `src/viz/app.py`

### Frontend (HTML/JavaScript)
- **Visualization**: Cytoscape.js with Dagre layout
- **Single Page**: `frontend/index.html`

## Node Schema (6 Types)
| Type | Color  | Description                                    |
| ---- | ------ | ---------------------------------------------- |
| HOST | Red    | Infrastructure targets (servers)               |
| CPE  | Orange | Software/products installed on hosts           |
| CVE  | Yellow | Vulnerabilities in software                    |
| CWE  | Green  | Weakness categories                            |
| TI   | Cyan   | Technical Impacts (what exploitation achieves) |
| VC   | Purple | Vector Changers (attacker capabilities)        |

## Graph Flow
```
ATTACKER → HOST → CPE → CVE → CWE → TI → VC
                                         ↓
                                    (ENABLES next attack)
```

**Edge Types:**
- `CAN_REACH` - Attacker to HOST
- `RUNS` - HOST to CPE
- `HAS_VULN` - CPE to CVE
- `IS_INSTANCE_OF` - CVE to CWE
- `HAS_IMPACT` - CWE to TI
- `LEADS_TO` - TI to VC
- `ENABLES` - VC enables further exploitation
- `HAS_STATE` - Initial VCs to ATTACKER

## Two-Layer Model
1. **Layer 1 (L1)**: DMZ/External network attacks
2. **Layer 2 (L2)**: Internal network attacks (after pivoting)

Bridge node: `INSIDE_NETWORK` connects L1 to L2

## Key Features

### Environment Filtering
- **UI Setting**: None (UI:N) or Required (UI:R)
- **AC Setting**: Low (AC:L) or High (AC:H)
- Filters CVEs based on CVSS requirements
- **Cascade filtering**: Filtered CVEs → CWE → TI → VC also dimmed

### Attacker Initial State
- Compound node "ATTACKER_BOX" contains:
  - Hacker node
  - Initial VCs: AV:N, PR:N
  - Environment VCs: UI, AC (dynamic)
- VCs point TO attacker (showing initial capabilities)

### Node Grouping Settings
Configure singular (per-parent) vs universal (shared) for:
- CPE (default: singular per-host)
- CVE (default: singular per-host)
- CWE (default: singular per-CVE)
- TI (default: singular per-CWE)
- VC (default: singular per-host)

### Interactive Features
- **Exploit Paths**: Highlights paths from ATTACKER to EXPLOITED (EX:Y) terminals
- **Hide/Restore**: H key hides selected nodes, creates bridge edges
- **Filter by Type**: Filter visibility by node type
- **Node Details**: Click to view full node data
- **Layouts**: Dagre (DAG), Breadthfirst, Force-directed, Circle

## Current Statistics
- **Total Nodes**: 175
- **Total Edges**: 218
- **Node Breakdown**: HOST:12, CPE:30, CVE:32, CWE:32, TI:32, VC:34, COMPOUND:1, ATTACKER:1, BRIDGE:1

## File Structure
```
PAGDrawer/
├── frontend/
│   └── index.html          # Full UI + Cytoscape visualization
├── src/
│   ├── core/
│   │   ├── schema.py       # NodeType, EdgeType enums
│   │   ├── config.py       # Graph configuration (grouping modes)
│   │   └── consensual_matrix.py  # TI → VC mappings
│   ├── data/
│   │   └── mock_data.py    # Sample network/vulnerability data
│   ├── graph/
│   │   └── builder.py      # KnowledgeGraphBuilder class
│   └── viz/
│       └── app.py          # FastAPI application
├── Docs/                   # Documentation notes
└── requirements.txt        # Python dependencies
```

## Dependencies
- Python: FastAPI, uvicorn, networkx
- Frontend: Cytoscape.js, cytoscape-dagre

## Running the Application
```bash
cd PAGDrawer
uvicorn src.viz.app:app --reload --host 0.0.0.0 --port 8000
# Open http://localhost:8000
```

## Recent Changes (2026-01-11)
- Added TI (Technical Impact) nodes between CWE and VC
- Implemented cascade environment filtering (CVE → CWE → TI → VC)
- Reversed VC edge direction (VCs point TO attacker)
- Fixed Exploit Paths to keep ATTACKER_BOX visible
- Fixed Restore All nodes logic for bridge edges
- Added TI to node grouping settings
