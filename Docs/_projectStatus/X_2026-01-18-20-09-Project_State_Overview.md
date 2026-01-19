# PAGDrawer - Project State Overview

**Date:** 2026-01-18
**Test Coverage:** 355 tests

---

## What is PAGDrawer?

PAGDrawer (Privilege-based Attack Graph Drawer) is a **vulnerability analysis and visualization tool** that transforms vulnerability scan data into interactive attack graphs. It models how an attacker could exploit vulnerabilities to escalate privileges and move through a network.

The project is based on academic research, specifically **Machalewski et al. (2024)** - "Expressing Impact of Vulnerabilities", which defines a **Consensual Transformation Matrix** for mapping technical impacts to privilege changes.

---

## Core Concept: The Attack Graph

The graph represents the attack surface of a system:

```
ATTACKER → HOST → CPE → CVE → CWE → TI → VC
   │         │      │      │      │    │    │
   │         │      │      │      │    │    └── Vector Changer (privilege state)
   │         │      │      │      │    └── Technical Impact (what attacker gains)
   │         │      │      │      └── Common Weakness (root cause)
   │         │      │      └── Vulnerability (specific CVE)
   │         │      └── Software (CPE identifier)
   │         └── Target machine
   └── Entry point
```

### Node Types

| Type         | Description            | Example                                   |
| ------------ | ---------------------- | ----------------------------------------- |
| **HOST**     | Target machines        | `host-001` (web server)                   |
| **CPE**      | Software/OS components | `cpe:2.3:a:apache:log4j:2.14.1`           |
| **CVE**      | Known vulnerabilities  | `CVE-2021-44228` (Log4Shell)              |
| **CWE**      | Weakness categories    | `CWE-78` (OS Command Injection)           |
| **TI**       | Technical Impacts      | "Execute Unauthorized Code or Commands"   |
| **VC**       | Vector Changers        | `AV:L`, `PR:H`, `EX:Y` (privilege levels) |
| **ATTACKER** | Entry point            | Single attacker node                      |
| **BRIDGE**   | L1→L2 transition       | Connects layers                           |
| **COMPOUND** | Multi-vuln chains      | Combined exploits                         |

### Edge Types

| Edge             | Meaning                                 |
| ---------------- | --------------------------------------- |
| `RUNS`           | Host runs software (HOST→CPE)           |
| `HAS_VULN`       | Software has vulnerability (CPE→CVE)    |
| `IS_INSTANCE_OF` | CVE is instance of weakness (CVE→CWE)   |
| `HAS_IMPACT`     | Weakness has technical impact (CWE→TI)  |
| `LEADS_TO`       | Impact leads to privilege state (TI→VC) |
| `ENABLES`        | State enables further attacks (VC→VC)   |

---

## Architecture

### Backend (Python/FastAPI)

```
src/
├── core/
│   ├── config.py           # Granularity configuration (grouping levels)
│   ├── consensual_matrix.py # TI→VC transformation rules
│   └── schema.py           # Node/Edge type definitions
├── data/
│   ├── loaders/
│   │   ├── base.py         # DataLoader abstraction
│   │   ├── trivy_loader.py # Trivy JSON parser
│   │   ├── cwe_fetcher.py  # CWE REST API client
│   │   ├── nvd_fetcher.py  # NVD API client
│   │   └── deployment_loader.py # YAML deployment config
│   ├── mock_data.py        # Sample vulnerability data
│   └── schemas/            # Pydantic models
├── graph/
│   └── builder.py          # Graph construction logic
└── viz/
    └── app.py              # FastAPI REST API
```

### Frontend (TypeScript/Vite)

```
frontend/
├── js/
│   ├── main.ts             # Entry point
│   ├── graph/              # Cytoscape.js graph rendering
│   ├── ui/                 # UI components (tooltips, controls)
│   ├── features/           # Feature modules (filtering, visibility)
│   ├── services/           # API communication
│   └── config/             # Configuration management
├── css/                    # Styles
└── index.html              # Single-page app
```

---

## Key Features

### 1. Data Sources

- **Mock Data**: Built-in sample vulnerabilities for testing
- **Trivy Integration**: Upload Trivy JSON scan results
- **Deployment Config**: YAML-based multi-host configuration

### 2. Granular Grouping

Nodes can be grouped at different levels to control graph complexity:

```
ATTACKER (universal) → HOST → CPE → CVE → CWE → TI → VC (most granular)
```

UI sliders let users adjust grouping per node type. For example:
- TI grouped by "CWE": Each CWE has its own TI nodes
- TI grouped by "ATTACKER": All CWEs share TI nodes globally

### 3. Two-Layer Attack Model

- **Layer 1 (L1)**: Initial exploitation (external attacker)
- **Layer 2 (L2)**: Post-compromise (lateral movement)

### 4. Consensual Transformation Matrix

Maps 24 Technical Impact categories to Vector Changer outcomes:

```python
"Execute Unauthorized Code or Commands" → [
    ("AV", "L"),   # Attacker gains local access
    ("PR", "H"),   # Attacker gains high privileges
    ("EX", "Y"),   # Code execution capability
]
```

### 5. Multi-TI Support

A single CWE can have multiple Technical Impacts:

```
CWE-78 ─┬─ TI:"Execute Unauthorized Code or Commands" → VC nodes
        ├─ TI:"Read Files or Directories" → VC nodes
        ├─ TI:"Modify Files or Directories" → VC nodes
        └─ TI:"Hide Activities" (no VC edges)
```

### 6. Interactive Visualization

- **Cytoscape.js** graph rendering
- Node tooltips with detailed information
- Visibility toggles per node type
- Reachability filtering
- Drag-and-drop layout

---

## API Endpoints

### Graph & Configuration

| Endpoint      | Method   | Description                  |
| ------------- | -------- | ---------------------------- |
| `/api/graph`  | GET      | Full graph as Cytoscape JSON |
| `/api/stats`  | GET      | Node/edge counts             |
| `/api/config` | GET/POST | Granularity configuration    |

### Data Upload

| Endpoint                      | Method | Description                           |
| ----------------------------- | ------ | ------------------------------------- |
| `/api/upload/trivy`           | POST   | Upload Trivy JSON file                |
| `/api/upload/trivy/json`      | POST   | Upload Trivy data as JSON body        |
| `/api/upload/deployment`      | POST   | Upload deployment YAML file           |
| `/api/upload/deployment/json` | POST   | Upload deployment config as JSON body |

### Data Management

| Endpoint            | Method | Description                      |
| ------------------- | ------ | -------------------------------- |
| `/api/data/status`  | GET    | Current source + upload counts   |
| `/api/data/rebuild` | POST   | Rebuild graph from uploaded data |
| `/api/data/reset`   | POST   | Reset to mock data               |
| `/api/data/trivy`   | DELETE | Clear uploaded Trivy data        |

---

## External Integrations

### 1. CWE REST API
Fetches Technical Impact mappings from MITRE's CWE database:
```
GET https://cweapi.mitre.org/api/v1/cwe/{id}
```

### 2. NVD API
Enriches CVE data (CVSS vectors, descriptions):
```
GET https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={id}
```

### 3. Trivy Scanner
Accepts JSON output from Aqua Trivy vulnerability scanner:
```bash
trivy image --format json postgres:latest > scan.json
```

---

## Current Graph Statistics (Mock Data)

| Metric      | Count |
| ----------- | ----- |
| Total Nodes | 273   |
| Total Edges | 458   |
| HOST        | 12    |
| CPE         | 30    |
| CVE         | 32    |
| CWE         | 32    |
| TI          | 130   |
| VC          | 34    |

---

## Development Status

### Completed Features
- Core graph model with all node/edge types
- Trivy integration with NVD/CWE enrichment
- Granular grouping configuration
- Multi-TI support (multiple impacts per CWE)
- Interactive web UI with Cytoscape.js
- Visibility toggles and reachability filtering
- Comprehensive test suite (355 tests)

### Running the Project

```bash
# Backend (port 8000)
./Scripts/start-backend.sh

# Frontend (port 3000)
./Scripts/start-frontend.sh

# Run tests
python -m pytest tests/ -v
```

### Tech Stack

| Component | Technology                     |
| --------- | ------------------------------ |
| Backend   | Python 3.10, FastAPI, NetworkX |
| Frontend  | TypeScript, Vite, Cytoscape.js |
| Testing   | pytest, Playwright (E2E)       |
| Data      | Pydantic, aiohttp              |

---

## Research Foundation

The project implements concepts from:

> **Machalewski et al. (2024)** - "Expressing Impact of Vulnerabilities"
>
> Defines the Consensual Transformation Matrix derived from expert consensus
> on 22 CVEs, mapping 24 Technical Impact categories to Vector Changer
> privilege states.

The matrix transforms vulnerability impacts into concrete privilege changes,
enabling attack path analysis and risk assessment.
