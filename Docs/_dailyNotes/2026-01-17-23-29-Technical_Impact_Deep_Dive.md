# Technical Impact (TI) Architecture Deep Dive - 2026-01-17

## Overview

This note provides a thorough analysis of the Technical Impact (TI) node implementation in PAGDrawer, including today's changes to the CWE REST API integration, the removal of "Varies" default values, and the TI label context system.

## Commits Since Last Daily Note

| Commit | Type | Description |
|--------|------|-------------|
| `f6e2d26` | fix | Show clean CWE ID in TI node labels |

## The Technical Impact (TI) Node Concept

### What is Technical Impact?

Technical Impact (TI) represents the **consequence** of exploiting a vulnerability. In the MITRE CWE database, each weakness has "Common Consequences" that describe what an attacker gains:

- **Execute Unauthorized Code or Commands** - RCE capability
- **Gain Privileges or Assume Identity** - Privilege escalation
- **Read Application Data** - Information disclosure
- **Modify Application Data** - Data tampering
- **DoS: Crash, Exit, or Restart** - Availability impact
- **Bypass Protection Mechanism** - Security control evasion

### TI in the Attack Graph

TI nodes sit between CWE and VC (Vector Changer) nodes in the graph flow:

```
CVE → CWE → TI → VC
        │
        └── "What can the attacker do after exploiting this weakness?"
```

Example chain:
```
CVE-2023-1234 → CWE-78 (OS Command Injection) → "Execute Unauthorized Code" → VC:PR:H (High Privileges)
```

## CWE REST API Integration

### The Old Approach (Before `3c54d95`)

Previously, the system downloaded a 30MB ZIP file from `cwe.mitre.org`:

```python
# OLD: XML-based approach
url = "https://cwe.mitre.org/data/xml/cwec_latest.xml.zip"
# Download, unzip, parse XML with ElementTree
# Extract Common_Consequences from XML structure
```

**Problems:**
1. 30MB download on first use
2. Complex XML parsing with namespaces
3. XML structure used underscores (`Common_Consequences`)
4. No real-time updates - had to re-download entire file

### The New Approach (After `3c54d95`)

Refactored to use the official MITRE CWE REST API:

```python
# NEW: REST API approach
CWE_API_BASE_URL = "https://cwe-api.mitre.org/api/v1"

def _fetch_from_api(self, cwe_id: str) -> Optional[List[str]]:
    url = f"{CWE_API_BASE_URL}/cwe/weakness/{numeric_id}"
    # Simple HTTP GET, parse JSON response
```

**API Endpoint:**
```
GET https://cwe-api.mitre.org/api/v1/cwe/weakness/{id}
```

**Response Structure:**
```json
{
  "Weaknesses": [{
    "ID": "354",
    "Name": "Improper Validation of Integrity Check Value",
    "Description": "The product does not validate...",
    "CommonConsequences": [
      {
        "Scope": ["Integrity"],
        "Impact": ["Modify Application Data"],
        "Note": "An attacker could modify..."
      },
      {
        "Scope": ["Non-Repudiation"],
        "Impact": ["Hide Activities"]
      }
    ]
  }]
}
```

**Key Implementation Details:**

1. **Response Wrapper**: API wraps data in `{"Weaknesses": [{...}]}`
   ```python
   def _extract_weakness_from_response(self, data):
       weaknesses = data.get("Weaknesses", [])
       return weaknesses[0] if weaknesses else None
   ```

2. **CamelCase Keys**: API uses `CommonConsequences` (not `Common_Consequences`)
   ```python
   consequences = data.get("CommonConsequences", [])  # camelCase!
   ```

3. **Impact Extraction**: Each consequence has `Impact` array
   ```python
   for consequence in consequences:
       impact_data = consequence.get("Impact", [])
       for impact in impact_data:
           normalized = self._normalize_impact(impact.strip())
   ```

### Benefits of REST API

| Aspect | XML Download | REST API |
|--------|--------------|----------|
| Initial load | 30MB download | ~2KB per CWE |
| Latency | Minutes (first time) | Milliseconds |
| Updates | Manual re-download | Real-time |
| Authentication | None | None required |
| Rate limits | N/A | Generous (no documented limit) |

## The "Varies" Problem and Solution

### The Problem (Before `b938008`)

When CWE data was unavailable or enrichment was disabled, the system defaulted to `"Varies"`:

```python
# OLD CODE
technical_impact = "Varies"  # Default fallback
if self._enrich_cwe and cwe_id != "CWE-noinfo":
    technical_impact = self.cwe_fetcher.get_primary_impact(...)
```

**Result:** Every CVE without CWE data created a TI node labeled "Varies", polluting the graph:

```
Before Fix:
- 128 TI nodes (36 were just "Varies" placeholders)
- 493 total nodes
- Graph cluttered with meaningless connections
```

### The Solution (After `b938008`)

Changed default to `None`, which the graph builder interprets as "skip TI node creation":

```python
# NEW CODE
technical_impact = None  # Won't create TI node if unknown
if self._enrich_cwe and cwe_id != "CWE-noinfo":
    technical_impact = self.cwe_fetcher.get_primary_impact(...)
```

**In `builder.py`:**
```python
def _wire_cwe_to_vcs(self, cwe_id, host_id, cvss_vector, technical_impact, ...):
    # Skip if no technical impact
    if not technical_impact:
        return  # No TI node created!
```

**Result:**
```
After Fix:
- 92 TI nodes (all meaningful impacts)
- 463 total nodes
- Graph shows only real attack consequences
```

### Impact Comparison Table

| Enrichment Setting | TI Nodes (Before) | TI Nodes (After) | Delta |
|--------------------|-------------------|------------------|-------|
| No enrichment | 128 ("Varies") | 0 | -128 |
| CWE enrichment on | 128 (92 real + 36 "Varies") | 92 | -36 |

## TI Node Labeling and Granularity

### The Granularity Problem

TI nodes can be grouped at different levels:

1. **Universal** - One TI node per impact type (e.g., one "Execute Unauthorized Code" node for entire graph)
2. **Per-CWE** - One TI node per CWE (e.g., "Execute Unauthorized Code" for CWE-78, another for CWE-94)
3. **Per-Host** - One TI node per host (most granular)

### The Label Problem (Before `f6e2d26`)

When using per-CWE granularity, TI node IDs included the full context path for proper grouping:

```python
ti_id = f"TI:{technical_impact[:20]}@{cwe_id}"
# Example: "TI:Execute Unauthoriz...@CWE-347@CVE-2011-3374@cpe:2.3:a:...@host_postgres_12345678"
```

The label was set to the same value, resulting in unreadable labels in the UI:

```
"Gain Privileges or A...\n(CWE-347@CVE-2011-3374@cpe:2.3:a:gnu:apt:2.6.1:*:*:*:*:*:*:*@host_postgres_f4df76b2)"
```

### The Solution (Commit `f6e2d26`)

Extract just the original CWE ID for the label while keeping full path in the ID:

```python
# Extract original CWE ID from full path
original_cwe = cwe_id.split("@")[0] if cwe_id else ""

if self.config.is_universal("TI"):
    ti_id = f"TI:{technical_impact[:20]}{layer_suffix}"  # universal within layer
    ti_label = ti_short
elif self.config.should_include_context("TI", "CWE"):
    ti_id = f"TI:{technical_impact[:20]}@{cwe_id}"  # per-CWE (most granular)
    ti_label = f"{ti_short}\n({original_cwe})"  # Clean label!
else:
    ti_id = f"TI:{technical_impact[:20]}@{host_id}"  # per-HOST
    ti_label = f"{ti_short}\n({host_id[:15] if host_id else ''})"
```

**Result:**
- **ID**: `TI:Execute Unauthoriz...@CWE-78@CVE-2023-...@cpe:...@host_x` (for proper grouping)
- **Label**: `"Execute Unauthoriz...\n(CWE-78)"` (clean, readable)

### ID vs Label Distinction

| Property | Node ID | Node Label |
|----------|---------|------------|
| Purpose | Unique identification, grouping | User display |
| Format | Full context path | Clean, readable |
| Example | `TI:Execute...@CWE-78@CVE-...@...` | `Execute...\n(CWE-78)` |
| Used by | Graph algorithms, edges | UI rendering |

## Data Flow: From Trivy to TI Node

```
1. Trivy JSON
   ├── VulnerabilityID: "CVE-2023-1234"
   ├── CweIDs: ["CWE-78"]
   └── Severity: "HIGH"
            │
            ▼
2. TrivyDataLoader._create_cve()
   ├── cwe_id = "CWE-78"
   └── technical_impact = cwe_fetcher.get_primary_impact("CWE-78")
            │
            ▼
3. CWEFetcher.get_primary_impact()
   ├── Check STATIC_CWE_MAPPING → Found: "Execute Unauthorized Code or Commands"
   └── Return first impact
            │
            ▼
4. CVE Data:
   {
     "id": "CVE-2023-1234",
     "cwe_id": "CWE-78",
     "technical_impact": "Execute Unauthorized Code or Commands"
   }
            │
            ▼
5. KnowledgeGraphBuilder._wire_cwe_to_vcs()
   ├── Creates TI node: "TI:Execute Unauthoriz...@CWE-78@..."
   ├── Sets label: "Execute Unauthoriz...\n(CWE-78)"
   └── Creates edges: CWE-78 → TI → VC:PR:H
```

## CWE Data Sources Hierarchy

The `CWEFetcher` uses a three-tier lookup:

### Tier 1: Static Mapping (Fastest)

Pre-defined mappings for ~70 common CWEs in `STATIC_CWE_MAPPING`:

```python
STATIC_CWE_MAPPING = {
    "CWE-78": ["Execute Unauthorized Code or Commands", "Read Files or Directories", ...],
    "CWE-89": ["Execute Unauthorized Code or Commands", "Read Application Data", ...],
    "CWE-79": ["Execute Unauthorized Code or Commands", "Bypass Protection Mechanism", ...],
    # ... ~70 more entries
}
```

### Tier 2: Local Cache

Persisted in `src/data/cache/cwe_cache.json`:

```json
{
  "impacts": {
    "CWE-354": ["Modify Application Data", "Hide Activities", "Other"],
    "CWE-347": ["Gain Privileges or Assume Identity"]
  },
  "info": {
    "CWE-354": {
      "id": "CWE-354",
      "name": "Improper Validation of Integrity Check Value",
      "description": "...",
      "technical_impacts": ["Modify Application Data", "Hide Activities", "Other"]
    }
  }
}
```

### Tier 3: REST API Fetch

If not in static mapping or cache, fetches from MITRE API:

```python
url = f"https://cwe-api.mitre.org/api/v1/cwe/weakness/{numeric_id}"
```

### Tier 4: Severity Fallback

If API fails, uses CVSS severity to estimate impact:

```python
SEVERITY_TO_IMPACT = {
    "CRITICAL": "Execute Unauthorized Code or Commands",
    "HIGH": "Gain Privileges or Assume Identity",
    "MEDIUM": "Bypass Protection Mechanism",
    "LOW": "Read Application Data",
    "UNKNOWN": "Other",
}
```

## Test Coverage

### CWE Fetcher Tests (`tests/test_cwe_fetcher.py`)

46 tests covering:
- Static mapping lookups
- Cache persistence and loading
- API response parsing
- Response wrapper extraction (`Weaknesses` array)
- Impact normalization
- Multiple CWE batch fetching
- Error handling (404, network failures)

### API-Specific Tests (13 new)

```python
def test_extract_weakness_from_response():
    """Test extracting weakness from API response wrapper."""

def test_extract_consequences_from_json():
    """Test extracting CommonConsequences (camelCase)."""

def test_normalize_impact():
    """Test impact text normalization."""
```

## Graph Statistics Comparison

### postgres:latest Scan Results

| Metric | Before Fixes | After All Fixes |
|--------|--------------|-----------------|
| Total Nodes | 493 | 463 |
| TI Nodes | 128 | 92 |
| "Varies" TI Nodes | 36 | 0 |
| CVE Nodes | ~128 | ~128 |
| CWE Nodes | ~45 | ~45 |
| VC Nodes | Variable | Variable |
| Total Edges | ~700 | 656 |

## Files Modified Today

| File | Changes |
|------|---------|
| `src/graph/builder.py` | Clean TI labels with `original_cwe` extraction |

## Files Modified in Previous Session

| File | Changes |
|------|---------|
| `src/data/loaders/cwe_fetcher.py` | Complete REST API rewrite |
| `src/data/loaders/trivy_loader.py` | Remove "Varies" default, fix NVD arg |
| `src/viz/app.py` | Preserve Trivy data on config change |
| `frontend/js/graph/layout.ts` | Exclude hidden elements from layout |
| `tests/test_cwe_fetcher.py` | Add 13 API-specific tests |

## Key Architectural Decisions

### 1. Why `None` Instead of Empty String?

Using `None` for unknown technical impact (not `""`) because:
- Explicit "no value" semantic
- Falsy check works: `if not technical_impact: return`
- Distinguishes "unknown" from "empty string by mistake"

### 2. Why Keep Full Path in TI ID?

The TI node ID includes full context (`@CWE-xxx@CVE-xxx@cpe-xxx@host-xxx`) because:
- Enables proper grouping in singular/universal modes
- Graph algorithms need unique identifiers
- Edge connections require stable IDs
- Label is separate - for human readability only

### 3. Why First Impact Only?

`get_primary_impact()` returns only the first impact because:
- Current architecture supports one TI per CWE→CVE relationship
- Multiple TIs would require parallel TI nodes (future enhancement)
- First impact is typically the most severe/relevant

## Future Considerations

1. **Multiple TI Support**: Create multiple TI nodes per CWE when `CommonConsequences` has multiple impacts
2. **TI Severity Weighting**: Order TI nodes by impact severity (RCE > Privilege Escalation > Info Disclosure)
3. **CWE Hierarchy**: Use parent CWE consequences when child CWE has none
4. **Batch API Optimization**: Currently fetches one CWE at a time; could batch but API returns minimal data for batch

## Server Status

- **Backend:** http://localhost:8000 (FastAPI/uvicorn)
- **Frontend:** http://localhost:3000 (Vite dev server)

---

## Appendix A: The Consensual Matrix - TI to VC Transformation

### What is the Consensual Matrix?

The Consensual Matrix (from Machalewski et al. 2024) defines how Technical Impacts translate into Vector Changer (VC) outcomes. This is the core of the attack graph logic - it answers: **"If an attacker achieves this impact, what capabilities do they gain?"**

Located in: `src/core/consensual_matrix.py`

### Impact Categories and VC Outcomes

#### High Impact (Full System Compromise)
These TIs result in `AV:L` (Local Access) + `PR:H` (High Privileges) + `EX:Y` (Exploited):

| Technical Impact | VC Outcomes | Meaning |
|-----------------|-------------|---------|
| Execute Unauthorized Code or Commands | AV:L, PR:H, EX:Y | Full RCE - attacker owns the system |
| Gain Privileges or Assume Identity | AV:L, PR:H, EX:Y | Privilege escalation complete |
| Modify Memory | AV:L, PR:H, EX:Y | Memory corruption leads to code exec |
| Modify Files or Directories | AV:L, PR:H, EX:Y | Can write to system files |
| Modify Application Data | AV:L, PR:H, EX:Y | Full data tampering |

#### Medium Impact (Partial Access)
These TIs result in `AV:L` (Local Access) and possibly `PR:H`:

| Technical Impact | VC Outcomes | Meaning |
|-----------------|-------------|---------|
| Read Memory | AV:L, PR:H | Can read sensitive memory (credentials) |
| Read Application Data | AV:L | Information disclosure |
| Read Files or Directories | AV:L | File system read access |
| Bypass Protection Mechanism | AV:L, PR:H | Auth bypass leads to privilege gain |

#### No Privilege Gain (DoS/Quality)
These TIs result in no VC gains (empty array):

| Technical Impact | VC Outcomes | Meaning |
|-----------------|-------------|---------|
| DoS: Crash, Exit, or Restart | [] | Availability impact only |
| DoS: Instability | [] | System becomes unstable |
| DoS: Resource Consumption (CPU) | [] | CPU exhaustion |
| DoS: Resource Consumption (Memory) | [] | Memory exhaustion |
| Hide Activities | [] | No direct privilege gain |
| Reduce Maintainability | [] | Code quality issue |
| Varies by Context | [] | Undefined - skipped |
| Other | [] | Unknown - skipped |

### VC Hierarchy Definitions

```python
# Attack Vector hierarchy (higher = closer access)
AV_HIERARCHY = {
    "N": 0,  # Network - remote access
    "A": 1,  # Adjacent - same network segment
    "L": 2,  # Local - on the machine
    "P": 3   # Physical - physical access required
}

# Privileges Required hierarchy (higher = more privilege)
PR_HIERARCHY = {
    "N": 0,  # None - unauthenticated
    "L": 1,  # Low - basic user
    "H": 2   # High - admin/root
}
```

### Escalation Logic

The builder only creates `YIELDS_STATE` edges when there's an **escalation**:

```python
# In builder.py: _wire_cwe_to_vcs()
for vc_type, vc_value in transformation["outcomes"]:
    is_escalation = True

    if vc_type == "AV":
        outcome_level = AV_HIERARCHY.get(vc_value, 0)
        prereq_level = prereq_levels.get("AV", 0)
        # AV escalation = moving "inward" (higher number)
        is_escalation = outcome_level > prereq_level
    elif vc_type == "PR":
        outcome_level = PR_HIERARCHY.get(vc_value, 0)
        prereq_level = prereq_levels.get("PR", 0)
        # PR escalation = gaining more privileges (higher number)
        is_escalation = outcome_level > prereq_level
    elif vc_type == "EX":
        is_escalation = True  # EX:Y always valid

    if is_escalation:
        # Create the VC node and edge
```

**Example:**
- CVE with CVSS `AV:N/PR:L/...` (starts remote, low privilege)
- TI = "Execute Unauthorized Code" → outcomes: `AV:L, PR:H, EX:Y`
- Escalation check:
  - `AV:N→L`: 0→2, escalation = True (gained local access)
  - `PR:L→H`: 1→2, escalation = True (gained admin)
  - `EX:Y`: Always True

---

## Appendix B: Complete Technical Impact Enumeration

The 24 Technical Impact categories defined in `consensual_matrix.py`:

### Category 1: Code/Command Execution
```python
EXECUTE_CODE = "Execute Unauthorized Code or Commands"
```

### Category 2: Privilege Escalation
```python
GAIN_PRIVILEGES = "Gain Privileges or Assume Identity"
```

### Category 3: Memory Operations
```python
MODIFY_MEMORY = "Modify Memory"
READ_MEMORY = "Read Memory"
```

### Category 4: File/Directory Operations
```python
MODIFY_FILES = "Modify Files or Directories"
READ_FILES = "Read Files or Directories"
```

### Category 5: Application Data Operations
```python
MODIFY_APP_DATA = "Modify Application Data"
READ_APP_DATA = "Read Application Data"
```

### Category 6: Denial of Service (6 variants)
```python
DOS_CRASH = "DoS: Crash, Exit, or Restart"
DOS_INSTABILITY = "DoS: Instability"
DOS_CPU = "DoS: Resource Consumption (CPU)"
DOS_MEMORY = "DoS: Resource Consumption (Memory)"
DOS_OTHER = "DoS: Resource Consumption (Other)"
DOS_AMPLIFICATION = "DoS: Amplification"
```

### Category 7: Security Bypass
```python
BYPASS_PROTECTION = "Bypass Protection Mechanism"
HIDE_ACTIVITIES = "Hide Activities"
```

### Category 8: Quality/Reliability
```python
REDUCE_MAINTAINABILITY = "Reduce Maintainability"
REDUCE_PERFORMANCE = "Reduce Performance"
REDUCE_RELIABILITY = "Reduce Reliability"
QUALITY_DEGRADATION = "Quality Degradation"
```

### Category 9: Logic/State
```python
ALTER_EXECUTION = "Alter Execution Logic"
UNEXPECTED_STATE = "Unexpected State"
```

### Category 10: Other
```python
VARIES_BY_CONTEXT = "Varies by Context"
OTHER = "Other"
```

---

## Appendix C: Real-World Example - CWE-354

During today's testing, CWE-354 was examined as a case study:

### CWE-354: Improper Validation of Integrity Check Value

**From MITRE API:**
```json
{
  "Weaknesses": [{
    "ID": "354",
    "Name": "Improper Validation of Integrity Check Value",
    "Description": "The product does not validate or incorrectly validates
                    the integrity check values or checksums of a message.",
    "CommonConsequences": [
      {
        "Scope": ["Integrity"],
        "Impact": ["Modify Application Data"],
        "Note": "An attacker could modify transferred data without detection..."
      },
      {
        "Scope": ["Non-Repudiation"],
        "Impact": ["Hide Activities"],
        "Note": "Exploitation of this weakness could allow an attacker to hide malicious activities..."
      },
      {
        "Scope": ["Other"],
        "Impact": ["Other"],
        "Note": "If integrity checks are used to determine system configuration..."
      }
    ]
  }]
}
```

**Extracted TIs:**
1. `Modify Application Data` → VCs: `AV:L, PR:H, EX:Y`
2. `Hide Activities` → VCs: `[]` (no privilege gain)
3. `Other` → VCs: `[]` (no privilege gain)

**Primary Impact Used:** `Modify Application Data` (first in list)

**Graph Result:**
```
CWE-354 → TI:"Modify Application..." → VC:AV:L → VC:PR:H → VC:EX:Y
              (CWE-354)
```

---

## Appendix D: TI Node Creation Code Walkthrough

### Step 1: TrivyDataLoader Creates CVE with TI

```python
# src/data/loaders/trivy_loader.py:307-312
def _create_cve(self, vuln: Vulnerability, cpe_id: str) -> Dict[str, Any]:
    cwe_id = vuln.CweIDs[0] if vuln.CweIDs else "CWE-noinfo"

    # Get technical impact (None if unknown)
    technical_impact = None
    if self._enrich_cwe and cwe_id != "CWE-noinfo":
        technical_impact = self.cwe_fetcher.get_primary_impact(
            cwe_id, severity=vuln.Severity, fetch_if_missing=True
        )

    return {
        "id": cve_id,
        "technical_impact": technical_impact,  # Used by builder
        # ...
    }
```

### Step 2: CWEFetcher Returns Primary Impact

```python
# src/data/loaders/cwe_fetcher.py:286-306
def get_primary_impact(self, cwe_id: str, severity: str = None,
                       fetch_if_missing: bool = True) -> str:
    impacts = self.get_technical_impacts(cwe_id, severity, fetch_if_missing)
    return impacts[0] if impacts else "Other"

def get_technical_impacts(self, cwe_id: str, ...):
    cwe_id = self._normalize_cwe_id(cwe_id)

    # Tier 1: Static mapping
    if cwe_id in STATIC_CWE_MAPPING:
        return STATIC_CWE_MAPPING[cwe_id]

    # Tier 2: Local cache
    if cwe_id in self._cache:
        return self._cache[cwe_id]

    # Tier 3: API fetch
    if fetch_if_missing:
        impacts = self._fetch_from_api(cwe_id)
        if impacts:
            self._cache[cwe_id] = impacts
            self._save_cache()
            return impacts

    # Tier 4: Severity fallback
    if severity:
        return [SEVERITY_TO_IMPACT[severity.upper()]]

    return ["Other"]
```

### Step 3: Builder Creates TI Node

```python
# src/graph/builder.py:234-260
def _wire_cwe_to_vcs(self, cwe_id: str, host_id: str, cvss_vector: str,
                     technical_impact: str, layer_suffix: str = ""):
    # Skip if no TI
    if not technical_impact:
        return

    # Shorten for display
    ti_short = technical_impact[:20] + "..." if len(technical_impact) > 20 else technical_impact

    # Extract clean CWE ID for label
    original_cwe = cwe_id.split("@")[0] if cwe_id else ""

    # Determine ID and label based on granularity
    if self.config.is_universal("TI"):
        ti_id = f"TI:{technical_impact[:20]}{layer_suffix}"
        ti_label = ti_short
    elif self.config.should_include_context("TI", "CWE"):
        ti_id = f"TI:{technical_impact[:20]}@{cwe_id}"  # Full path for grouping
        ti_label = f"{ti_short}\n({original_cwe})"      # Clean for display
    else:
        ti_id = f"TI:{technical_impact[:20]}@{host_id}"
        ti_label = f"{ti_short}\n({host_id[:15] if host_id else ''})"

    # Create node
    if not self.graph.has_node(ti_id):
        self.graph.add_node(
            ti_id,
            node_type="TI",
            impact=technical_impact,
            label=ti_label,  # This is what UI shows
            description=f"Technical Impact: {technical_impact}",
            layer="L2" if layer_suffix else "L1"
        )

    # Create CWE → TI edge
    if cwe_id and self.graph.has_node(cwe_id):
        self.graph.add_edge(cwe_id, ti_id, edge_type="HAS_IMPACT")
```

### Step 4: TI Connects to VC Outcomes

```python
# src/graph/builder.py:271-310
    # Get VC outcomes from Consensual Matrix
    transformation = transform_cve_to_vc_edges(cwe_id, cvss_vector, technical_impact)

    for vc_type, vc_value in transformation["outcomes"]:
        # Check escalation (skip if not a privilege gain)
        is_escalation = True
        if vc_type == "AV":
            is_escalation = AV_HIERARCHY[vc_value] > prereq_levels.get("AV", 0)
        elif vc_type == "PR":
            is_escalation = PR_HIERARCHY[vc_value] > prereq_levels.get("PR", 0)

        if is_escalation:
            # Create VC node
            vc_id = f"VC:{vc_type}:{vc_value}@{host_id}" if host_id else f"VC:{vc_type}:{vc_value}"

            if not self.graph.has_node(vc_id):
                self.graph.add_node(vc_id, node_type="VC", vc_type=vc_type, value=vc_value)

            # Create TI → VC edge
            self.graph.add_edge(ti_id, vc_id, edge_type="YIELDS_STATE")
```

---

## Appendix E: Debugging TI Issues

### Common Problems and Solutions

#### Problem 1: TI Node Not Created
**Symptom:** CVE has CWE but no TI node in graph
**Check:**
```python
# 1. Is enrichment enabled?
loader = TrivyDataLoader(enrich_cwe=True)  # Must be True

# 2. Is CWE valid?
if cwe_id == "CWE-noinfo":
    # No TI will be created

# 3. Is technical_impact None?
if not technical_impact:
    return  # _wire_cwe_to_vcs exits early
```

#### Problem 2: TI Label Shows Full Path
**Symptom:** Label shows `CWE-354@CVE-...@cpe-...@host-...`
**Fix:** Apply commit `f6e2d26` - extracts `original_cwe = cwe_id.split("@")[0]`

#### Problem 3: Too Many TI Nodes
**Symptom:** Graph has 128 TI nodes but only 45 CWEs
**Cause:** Each CVE creates its own TI even with same impact
**Fix:** Use universal TI mode: `config.set_universal("TI", True)`

#### Problem 4: "Varies" TI Nodes Everywhere
**Symptom:** Many TI nodes labeled "Varies by Context"
**Cause:** Using old code with `technical_impact = "Varies"` default
**Fix:** Apply commit `b938008` - sets `technical_impact = None` when unknown

### Verification Commands

```python
# Count TI nodes
ti_count = len([n for n in graph.nodes if graph.nodes[n].get('node_type') == 'TI'])

# List unique TI impacts
unique_tis = set(graph.nodes[n].get('impact') for n in graph.nodes
                 if graph.nodes[n].get('node_type') == 'TI')

# Check for "Varies" pollution
varies_count = len([n for n in graph.nodes
                    if graph.nodes[n].get('impact') == 'Varies by Context'])
```

---

## Summary

The Technical Impact system now:
1. Uses MITRE REST API for real-time CWE data
2. Shows only meaningful impacts (no "Varies" pollution)
3. Displays clean labels like `"Execute Unauthoriz...\n(CWE-78)"`
4. Maintains proper grouping via detailed node IDs
5. Has comprehensive test coverage (46 tests)
6. Correctly transforms TI → VC using the Consensual Matrix
7. Only creates VC edges for actual privilege escalations
