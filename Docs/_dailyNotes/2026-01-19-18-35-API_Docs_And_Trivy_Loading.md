# API Documentation & Trivy Data Loading

**Date:** 2026-01-19  
**Focus:** Documentation fixes, Trivy scan workflow exploration

---

## Summary

Session focused on understanding and documenting the Trivy data loading workflow, testing API endpoints, and fixing outdated documentation.

---

## Changes Made

### 1. Documentation Update - API Endpoints

**File:** `Docs/_projectStatus/X_2026-01-18-20-09-Project_State_Overview.md`

Fixed outdated API endpoint documentation. The original docs listed non-existent endpoints:
- ❌ `/api/trivy/upload` 
- ❌ `/api/trivy/scans`
- ❌ `/api/deployment/upload`

Replaced with actual endpoints organized by category:

#### Graph & Configuration
| Endpoint      | Method   | Description                  |
| ------------- | -------- | ---------------------------- |
| `/api/graph`  | GET      | Full graph as Cytoscape JSON |
| `/api/stats`  | GET      | Node/edge counts             |
| `/api/config` | GET/POST | Granularity configuration    |

#### Data Upload
| Endpoint                      | Method | Description                                       |
| ----------------------------- | ------ | ------------------------------------------------- |
| `/api/upload/trivy`           | POST   | Upload Trivy JSON file (form-data, field: `file`) |
| `/api/upload/trivy/json`      | POST   | Upload Trivy data as raw JSON body                |
| `/api/upload/deployment`      | POST   | Upload deployment YAML file                       |
| `/api/upload/deployment/json` | POST   | Upload deployment config as JSON body             |

#### Data Management
| Endpoint            | Method | Description                      |
| ------------------- | ------ | -------------------------------- |
| `/api/data/status`  | GET    | Current source + upload counts   |
| `/api/data/rebuild` | POST   | Rebuild graph from uploaded data |
| `/api/data/reset`   | POST   | Reset to mock data               |
| `/api/data/trivy`   | DELETE | Clear uploaded Trivy data        |

---

## Trivy Loading Workflow

Documented the complete workflow for loading Trivy scans:

### Step 1: Upload Trivy Scan
```powershell
# Option A: Raw JSON body
$json = Get-Content "examples\trivy_postgres_latest_scan.json" -Raw -Encoding UTF8
Invoke-RestMethod -Uri "http://localhost:8000/api/upload/trivy/json" `
    -Method Post -ContentType "application/json; charset=utf-8" `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($json))

# Option B: File upload via Postman
# POST /api/upload/trivy with form-data, key: "file"
```

**Response:** `{"status": "ok", "message": "Trivy data uploaded successfully", "total_uploaded": 1}`

### Step 2: Rebuild Graph
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/data/rebuild?enrich=true" -Method Post
```

---

## Enrich Parameter Deep Dive

Investigated what `enrich=true` does in `/api/data/rebuild`:

### `enrich=false` (fast, offline)
- Uses only data from Trivy JSON
- No external API calls
- Graph missing TI/VC nodes

### `enrich=true` (slower, complete graph)
1. **CWE API calls** - Fetches Technical Impact mappings from MITRE CWE REST API
2. **NVD API calls** - Fetches missing CVSS vectors, EPSS scores, descriptions
3. **Both cached** - Data persisted to `src/data/cache/*.json`

### Comparison Results (PostgreSQL scan)

| Metric      | enrich=false | enrich=true |
| ----------- | ------------ | ----------- |
| Total Nodes | 367          | 629 (+72%)  |
| Total Edges | 362          | 958 (+165%) |
| TI Nodes    | 0            | 238         |
| VC Nodes    | 2            | 14          |

---

## Available Trivy Scan Files

Located in `examples/`:
- `trivy_postgres_scan.json`
- `trivy_postgres_latest_scan.json`
- `trivy_postgres17_scan.json`
- `sample_trivy_scan.json`

---

## Commits

- `7448f36` - chore: update CLAUDE agent settings
