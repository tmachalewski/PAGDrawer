# PAGDrawer - Project State Overview
**Date:** 2026-01-17 18:57
**Status:** Trivy Integration Complete - Real Vulnerability Data Support

## Project Summary
**PAGDrawer** (Predictive Attack Graph Drawer) is a visualization tool for security attack graphs. It models how vulnerabilities across a network can be exploited to gain privileges and pivot laterally through systems.

**NEW:** Now supports loading real vulnerability data from Trivy scanner!

---

## Architecture

### Backend (Python/FastAPI)
| Component     | Technology        |
| ------------- | ----------------- |
| Framework     | FastAPI + Uvicorn |
| Graph Library | NetworkX          |
| Data Loaders  | Trivy, NVD, CWE   |
| Entry Point   | `src/viz/app.py`  |
| Port          | 8000              |

### Frontend (TypeScript/Vite)
| Component     | Technology                  |
| ------------- | --------------------------- |
| Build Tool    | Vite                        |
| Visualization | Cytoscape.js + Dagre layout |
| Language      | TypeScript (strict mode)    |
| Port          | 3000 (dev server)           |

---

## NEW: Trivy Integration (Jan 17, 2026)

### Data Pipeline
```
Trivy JSON → TrivyDataLoader → LoadedData → KnowledgeGraphBuilder → Graph
                    ↑
         DeploymentConfig (optional network topology)
```

### Data Loaders
| Loader | Purpose |
|--------|---------|
| `MockDataLoader` | Built-in sample data |
| `TrivyDataLoader` | Parse Trivy JSON scans |
| `DeploymentLoader` | Merge scans with network topology |
| `CWEFetcher` | CWE → Technical Impact mapping |
| `NVDFetcher` | NVD API + EPSS scores |

### New API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/upload/trivy` | Upload Trivy JSON file |
| POST | `/api/upload/trivy/json` | Upload Trivy JSON directly |
| POST | `/api/upload/deployment` | Upload deployment YAML |
| POST | `/api/upload/deployment/json` | Upload deployment config |
| GET | `/api/data/status` | Check upload status |
| POST | `/api/data/rebuild` | Rebuild graph from uploads |
| POST | `/api/data/reset` | Reset to mock data |
| DELETE | `/api/data/trivy` | Clear uploaded Trivy data |

### Deployment Configuration (YAML)
Define network topology and map Trivy targets to hosts:
```yaml
version: "1.0"
name: "Production Environment"

subnets:
  - id: dmz
    connects_to: [internal]
  - id: internal

hosts:
  - id: postgres-db
    criticality_score: 0.9
    subnet_id: internal
    trivy_targets:
      - "postgres:*"
      - "*gosu*"
```

### Real-World Testing Results
Scanned PostgreSQL images:

| Version | PostgreSQL | CRITICAL | HIGH | MEDIUM | LOW | Total |
|---------|------------|----------|------|--------|-----|-------|
| postgres:15 | 15.x | 0 | 7 | 34 | 101 | **142** |
| postgres:17 | 17.x | 0 | 9 | 36 | 101 | **146** |
| postgres:latest | 18.1 | 0 | 7 | 34 | 101 | **142** |

Graph from postgres:latest: **493 nodes, 489 edges**

---

## Node Schema (7 Types)

| Type     | Color  | Description                               |
| -------- | ------ | ----------------------------------------- |
| HOST     | Red    | Infrastructure targets (servers)          |
| CPE      | Orange | Software/products installed on hosts      |
| CVE      | Yellow | Vulnerabilities in software               |
| CWE      | Green  | Weakness categories                       |
| TI       | Cyan   | Technical Impacts (exploitation outcomes) |
| VC       | Purple | Vector Changers (attacker capabilities)   |
| ATTACKER | Gold   | Threat actor starting point               |

## Graph Flow
```
ATTACKER → HOST → CPE → CVE → CWE → TI → VC
                                          ↓
                                    (ENABLES next attack)
```

**Edge Types:**
| Edge           | Direction       | Description             |
| -------------- | --------------- | ----------------------- |
| CAN_REACH      | ATTACKER → HOST | Network accessibility   |
| RUNS           | HOST → CPE      | Software installation   |
| HAS_VULN       | CPE → CVE       | Vulnerability presence  |
| IS_INSTANCE_OF | CVE → CWE       | Weakness classification |
| HAS_IMPACT     | CWE → TI        | Impact from weakness    |
| LEADS_TO       | TI → VC         | Capability gained       |
| ENABLES        | VC → CVE        | Multi-stage attack      |
| HAS_STATE      | VC → ATTACKER   | Initial capabilities    |
| PIVOTS_TO      | VC → HOST       | Lateral movement        |
| BRIDGE         | any → any       | Visual connector        |

---

## Key Features

### 1. Real Vulnerability Data (NEW)
- Load Trivy JSON scans via API or Python
- Optional enrichment from NVD (CVSS, EPSS scores)
- CWE → Technical Impact mapping (70+ CWEs)
- Deployment topology configuration

### 2. Environment Filtering
- **UI Setting**: None (UI:N) or Required (UI:R)
- **AC Setting**: Low (AC:L) or High (AC:H)
- Cascade filtering: CVE → CWE → TI → VC

### 3. Reachability Filtering
- **Reachable hosts** (via CAN_REACH): Full opacity
- **Unreachable L1 hosts**: Dimmed (30% opacity)
- **L2 hosts**: Always reachable via jump hosts

### 4. Granular Grouping Sliders
Each node type has a slider controlling grouping:

| Node Type | Slider Options                      |
| --------- | ----------------------------------- |
| CPE       | ATTACKER, HOST                      |
| CVE       | ATTACKER, HOST, CPE                 |
| CWE       | ATTACKER, HOST, CPE, CVE            |
| TI        | ATTACKER, HOST, CPE, CVE, CWE       |
| VC        | ATTACKER, HOST, CPE, CVE, CWE, TI   |

### 5. Visibility Toggles
- Toggle buttons (👁) for each node type
- Bridge edges maintain connectivity when hiding
- Settings persist across graph rebuilds

### 6. Hide Selected / Restore All
- Remove individual nodes with bridge edges
- Restore all brings back hidden nodes

### 7. Interactive Tooltips
- Hover shows node details
- Click to pin, CTRL+Click for multiple
- Draggable tooltips

---

## File Structure

```
PAGDrawer/
├── frontend/
│   ├── index.html
│   ├── vite.config.ts
│   ├── css/styles.css
│   └── js/
│       ├── main.ts
│       ├── types.ts
│       ├── config/constants.ts
│       ├── services/api.ts
│       ├── graph/{core,layout,events}.ts
│       ├── features/{filter,environment,hideRestore,exploitPaths}.ts
│       └── ui/{sidebar,modal,tooltip}.ts
├── src/
│   ├── core/
│   │   ├── schema.py
│   │   ├── config.py
│   │   └── consensual_matrix.py
│   ├── data/
│   │   ├── mock_data.py
│   │   ├── loaders/                    # NEW
│   │   │   ├── base.py                 # DataLoader ABC, LoadedData
│   │   │   ├── mock_loader.py          # Mock data wrapper
│   │   │   ├── trivy_loader.py         # Trivy JSON parser
│   │   │   ├── deployment_loader.py    # Deployment config + merge
│   │   │   ├── cwe_fetcher.py          # CWE → Technical Impact
│   │   │   └── nvd_fetcher.py          # NVD API + EPSS
│   │   └── schemas/                    # NEW
│   │       ├── trivy.py                # Trivy JSON Pydantic models
│   │       └── deployment.py           # Deployment YAML models
│   ├── graph/builder.py
│   └── viz/app.py                      # + new upload endpoints
├── tests/
│   ├── test_builder.py
│   ├── test_api.py
│   ├── test_config.py
│   ├── test_schema.py
│   ├── test_frontend.py
│   ├── test_data_loaders.py            # NEW
│   ├── test_cwe_fetcher.py             # NEW
│   ├── test_nvd_fetcher.py             # NEW
│   ├── test_trivy_loader.py            # NEW
│   ├── test_deployment_loader.py       # NEW
│   └── test_api_endpoints.py           # NEW
├── examples/                           # NEW
│   ├── sample_deployment.yaml
│   ├── sample_trivy_scan.json
│   ├── postgres_deployment.yaml
│   ├── trivy_postgres_scan.json        # Real scan (142 CVEs)
│   ├── trivy_postgres17_scan.json      # Real scan (146 CVEs)
│   ├── trivy_postgres_latest_scan.json # Real scan (142 CVEs)
│   └── demo_trivy_integration.py
└── Docs/
    ├── _dailyNotes/
    └── _projectStatus/
```

---

## Test Coverage

### Python Backend
| Suite                    | Tests | Description                |
| ------------------------ | ----- | -------------------------- |
| Core Tests               | 101   | Schema, config, builder    |
| Data Loader Tests        | 31    | Base loader abstraction    |
| CWE Fetcher Tests        | 33    | CWE → TI mapping           |
| NVD Fetcher Tests        | 26    | NVD API + EPSS             |
| Trivy Loader Tests       | 33    | Trivy JSON parsing         |
| Deployment Loader Tests  | 23    | Deployment config          |
| API Endpoint Tests       | 17    | Upload/rebuild endpoints   |
| **Backend Total**        | **291** |                          |

### Frontend Tests
| Suite                | Tests | Framework         |
| -------------------- | ----- | ----------------- |
| TypeScript Unit      | 9     | Vitest            |
| Playwright E2E       | 67    | pytest-playwright |
| **Frontend Total**   | **76** |                  |

### **Grand Total: 367 tests**

---

## API Endpoints

### Graph API
| Method | Endpoint      | Description                  |
| ------ | ------------- | ---------------------------- |
| GET    | /api/graph    | Fetch full graph data        |
| GET    | /api/stats    | Get node/edge statistics     |
| GET    | /api/config   | Get current configuration    |
| POST   | /api/config   | Update graph configuration   |

### Data Management API (NEW)
| Method | Endpoint                  | Description                  |
| ------ | ------------------------- | ---------------------------- |
| POST   | /api/upload/trivy         | Upload Trivy JSON file       |
| POST   | /api/upload/trivy/json    | Upload Trivy JSON directly   |
| POST   | /api/upload/deployment    | Upload deployment YAML       |
| POST   | /api/upload/deployment/json | Upload deployment config   |
| GET    | /api/data/status          | Check upload status          |
| POST   | /api/data/rebuild         | Rebuild graph from uploads   |
| POST   | /api/data/reset           | Reset to mock data           |
| DELETE | /api/data/trivy           | Clear uploaded Trivy data    |

---

## Running the Project

### Quick Start with Real Data
```bash
# Terminal 1: Start backend
cd PAGDrawer
uvicorn src.viz.app:app --reload --port 8000

# Terminal 2: Start frontend
cd frontend
npm run dev

# Terminal 3: Upload Trivy scan
curl -X POST "http://localhost:8000/api/upload/trivy" \
  -F "file=@examples/trivy_postgres_latest_scan.json"
curl -X POST "http://localhost:8000/api/upload/deployment" \
  -F "file=@examples/postgres_deployment.yaml"
curl -X POST "http://localhost:8000/api/data/rebuild?enrich=false"

# Open http://localhost:3000
```

### Run Trivy Scan (requires Docker)
```bash
docker run --rm aquasec/trivy:latest image -f json postgres:latest > scan.json
```

### Run Tests
```bash
# All backend tests
python -m pytest tests/ --ignore=tests/e2e/ --ignore=tests/test_frontend.py

# With coverage
python -m pytest --cov=src --cov-report=term-missing

# Single test file
python -m pytest tests/test_trivy_loader.py -v
```

### Python API
```python
from src.data.loaders import load_deployment

data = load_deployment(
    config_path="deployment.yaml",
    trivy_paths=["scan.json"],
    enrich=True  # Fetch from NVD/CWE
)
```

---

## Dependencies

### Python (requirements.txt)
```
fastapi
uvicorn
networkx
pydantic
pyyaml
python-multipart
requests  # For NVD/CWE fetchers
```

### Node.js (frontend/package.json)
```
cytoscape
cytoscape-dagre
vite
vitest
typescript
```

---

## Recent Commits (Jan 17, 2026)

```
00930b2 feat(api): add endpoints for Trivy data upload and management
afdb02e feat(loaders): implement deployment configuration and loader
7c44c73 feat(loaders): implement TrivyDataLoader for Trivy JSON parsing
5aa8b65 feat(loaders): implement NVD fetcher for CVE enrichment
39b81cf feat(data): add CWE fetcher for Technical Impact mapping
```

---

## Known Limitations

1. **NVD Rate Limiting**: Without API key, limited to 5 requests/30s
2. **EPSS Data**: May not exist for very new CVEs
3. **CWE Coverage**: 70+ CWEs mapped, others use severity fallback
4. **Single User**: No session management

---

## Future Enhancements (Potential)

- ~~Real vulnerability data integration~~ ✅ DONE
- Session persistence for visibility/filter state
- Export graph to various formats (PNG, SVG, JSON)
- Attack path analysis with probability scoring
- CI/CD pipeline for automated scans
- Multi-tenant support
