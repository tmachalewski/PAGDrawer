# Multi-TI Feature Implementation

**Date:** 2026-01-18
**Status:** Completed
**Related Issues:** Enhanced attack graph granularity

## Overview

Implemented support for multiple Technical Impact (TI) nodes per CWE. Previously, only the first impact from a CWE's CommonConsequences was used. Now all impacts are represented as separate TI nodes connected to the CWE.

## Problem Statement

CWEs like CWE-78 (OS Command Injection) have multiple technical impacts:
- Execute Unauthorized Code or Commands
- Read Files or Directories
- Modify Files or Directories
- Hide Activities

The original implementation only used the first impact, losing valuable attack surface information.

## Architecture Change

### Before
```
CWE-78 → TI:"Execute..." → VC nodes (only first impact)
```

### After
```
CWE-78 ─┬─ TI:"Execute Unauthoriz..." → VC:AV:L, VC:PR:H, VC:EX:Y
        ├─ TI:"Read Files or Dire..." → VC:AV:L
        ├─ TI:"Modify Files or Di..." → VC:AV:L, VC:PR:H, VC:EX:Y
        └─ TI:"Hide Activities" (no VC edges if non-escalating)
```

## Files Modified

### 1. `src/data/mock_data.py`

Changed all CVE entries from `technical_impact` (string) to `technical_impacts` (list).

**Example - CWE-78 (OS Command Injection):**
```python
# Before
"technical_impact": "Execute Unauthorized Code"

# After
"technical_impacts": [
    "Execute Unauthorized Code or Commands",
    "Read Files or Directories",
    "Modify Files or Directories",
    "Hide Activities"
]
```

**Realistic multi-impact values by CWE:**

| CWE | Impacts |
|-----|---------|
| CWE-78 | Execute Code, Read Files, Modify Files, Hide Activities |
| CWE-119 | Execute Code, Gain Privileges, Modify Memory, Read Memory, DoS |
| CWE-89 | Read App Data, Modify App Data, Bypass Protection |
| CWE-79 | Execute Code, Read App Data, Bypass Protection |
| CWE-22 | Execute Code, Read Files, Modify Files |
| CWE-20 | Execute Code |

### 2. `src/data/loaders/base.py`

Updated validation and docstring:

```python
# Line 49 - Docstring
- technical_impacts: List[str] (list of impacts for consensual matrix transformation)

# Line 99 - Validation
for field in ["id", "description", "epss_score", "cvss_vector", "cpe_id", "cwe_id", "technical_impacts"]:
```

### 3. `src/data/loaders/trivy_loader.py`

Changed from `get_primary_impact()` to `get_technical_impacts()`:

```python
# Line 308-312
technical_impacts = []
if self._enrich_cwe and cwe_id != "CWE-noinfo":
    technical_impacts = self.cwe_fetcher.get_technical_impacts(
        cwe_id, severity=vuln.Severity, fetch_if_missing=True
    )

# Line 349 - Return dict
"technical_impacts": technical_impacts,
```

### 4. `src/graph/builder.py`

#### Method Signature Change (line 201)
```python
# Before
def _wire_cwe_to_vcs(self, cwe_id, host_id, cvss_vector, technical_impact, layer_suffix=""):

# After
def _wire_cwe_to_vcs(self, cwe_id, host_id, cvss_vector, technical_impacts: List[str], layer_suffix=""):
```

#### Loop Implementation (lines 225-318)
```python
# Process each technical impact
for technical_impact in technical_impacts:
    transformation = transform_cve_to_vc_edges(cwe_id, cvss_vector, technical_impact)

    # Build prereq lookup for escalation checking
    prereq_levels = {}
    for vc_type, vc_value in transformation["prerequisites"]:
        if vc_type == "AV":
            prereq_levels["AV"] = AV_HIERARCHY.get(vc_value, 0)
        elif vc_type == "PR":
            prereq_levels["PR"] = PR_HIERARCHY.get(vc_value, 0)

    # Create TI node (Technical Impact)
    ti_short = technical_impact[:20] + "..." if len(technical_impact) > 20 else technical_impact
    # ... rest of TI creation logic

    # Create outcome VCs connected FROM TI (only for escalations)
    for vc_type, vc_value in transformation["outcomes"]:
        # ... VC creation logic
```

#### Calling Site Update (line 518)
```python
# Before
cve_data.get("technical_impact", "")

# After
cve_data.get("technical_impacts", [])
```

### 5. Test Files Updated

| File | Changes |
|------|---------|
| `tests/test_builder.py` | 3 tests: empty list check, single impact, no host_id |
| `tests/test_data_loaders.py` | 4 CVE entries in test data |
| `tests/test_trivy_loader.py` | 2 tests: field check, mock method |
| `tests/test_cwe_fetcher.py` | 1 test: iterate over impacts list |

## TI Node ID Strategy

The impact text itself makes IDs unique - no additional differentiator needed:

```python
# Examples for CWE-78 with 4 impacts:
TI:Execute Unauthoriz...@CWE-78@...  # Truncated at 20 chars
TI:Read Files or Dire...@CWE-78@...
TI:Modify Files or Di...@CWE-78@...
TI:Hide Activities@CWE-78@...        # Short enough, no truncation
```

## Expected Graph Impact

| Metric | Before (Est.) | After (Est.) |
|--------|---------------|--------------|
| TI nodes | ~92 | ~150-200 |
| Total nodes | ~463 | ~520-580 |
| Edges | ~656 | ~750-850 |

## Test Results

```
352 passed, 1 failed (pre-existing unrelated config test)
```

All Multi-TI related tests pass:
- `test_skips_empty_technical_impacts` - Verifies empty list handling
- `test_creates_ti_node_with_valid_impact` - Verifies TI creation
- `test_creates_vc_without_host_id` - Verifies layer suffix handling
- `test_cve_has_required_fields` - Verifies `technical_impacts` field
- `test_enrichment_fetches_technical_impacts` - Verifies CWE fetcher integration

## Verification Steps

1. **Run tests:**
   ```bash
   python -m pytest tests/ -v
   ```

2. **Restart backend server**

3. **Load Trivy scan via UI**

4. **Check TI node count:**
   ```bash
   curl http://localhost:8000/api/graph | python -c "
   import sys, json
   data = json.load(sys.stdin)
   ti_nodes = [n for n in data['elements']['nodes'] if n['data']['type'] == 'TI']
   print(f'TI nodes: {len(ti_nodes)}')
   "
   ```

5. **Verify in UI:** Find CWE-78 → should connect to multiple TI nodes

## Design Decisions

1. **Empty List Handling:** `_wire_cwe_to_vcs()` returns early if `technical_impacts` is empty, preventing orphan nodes.

2. **Escalation Filtering:** Each TI→VC edge is still filtered by escalation logic. Non-escalating impacts (like "Hide Activities") may not create VC edges.

3. **Backward Compatibility:** The `get_technical_impacts()` method was already available in CWE fetcher; we just switched from `get_primary_impact()`.

4. **Consensual Matrix:** No changes needed - `transform_cve_to_vc_edges()` still takes a single impact string; the builder loops through the list.

## Related Components (No Changes Needed)

| Component | Reason |
|-----------|--------|
| `cwe_fetcher.py` | `get_technical_impacts()` already returns list |
| `consensual_matrix.py` | Each impact maps independently to VCs |
| `config.py` | Granularity config already supports multi-TI |
| `tests/conftest.py` | Already uses `technical_impacts` list format |

## Future Considerations

1. **Impact Deduplication:** If the same impact appears in multiple CWEs on the same host, consider whether to merge TI nodes.

2. **Impact Prioritization:** Some impacts may be more relevant for attack chains than others.

3. **UI Visualization:** Consider grouping or collapsing multiple TI nodes for cleaner visualization.
