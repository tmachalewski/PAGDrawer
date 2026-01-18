# CWE REST API Refactoring

**Date:** 2026-01-17 20:57

## Summary

Refactored the CWE fetcher to use the official MITRE CWE REST API instead of downloading and parsing the XML dataset.

## Changes Made

### CWE Fetcher (`src/data/loaders/cwe_fetcher.py`)

**Before:**
- Downloaded 30MB ZIP file from `cwe.mitre.org/data/xml/cwec_latest.xml.zip`
- Parsed XML with ElementTree
- Extracted `Common_Consequences` from XML elements

**After:**
- Uses REST API at `https://cwe-api.mitre.org/api/v1/`
- Simple HTTP GET requests per CWE
- Parses JSON response with `CommonConsequences` field

### API Details

| Endpoint | Description |
|----------|-------------|
| `/cwe/weakness/{id}` | Get single weakness with full details |
| `/cwe/{id1},{id2}` | Get multiple weaknesses (minimal data only) |

**Response structure:**
```json
{
  "Weaknesses": [{
    "ID": "354",
    "Name": "Improper Validation of Integrity Check Value",
    "CommonConsequences": [
      {"Scope": ["Integrity"], "Impact": ["Modify Application Data"]},
      {"Scope": ["Non-Repudiation"], "Impact": ["Hide Activities"]}
    ]
  }]
}
```

### New Methods

| Method | Description |
|--------|-------------|
| `_extract_weakness_from_response()` | Unwraps API response wrapper |
| `_extract_consequences_from_json()` | Parses CommonConsequences array |
| `_get_numeric_id()` | Extracts numeric ID from "CWE-XXX" |
| `fetch_multiple()` | Fetches multiple CWEs (individual calls) |

### Bug Fix

Fixed argument name in `trivy_loader.py:70`:
```python
# Before (incorrect)
self._nvd_fetcher = NVDFetcher(api_key=self._nvd_api_key)

# After (correct)
self._nvd_fetcher = NVDFetcher(nvd_api_key=self._nvd_api_key)
```

## Testing

### CWE-354 Example

```python
from src.data.loaders.cwe_fetcher import CWEFetcher

fetcher = CWEFetcher()
impacts = fetcher.get_technical_impacts('CWE-354')
# Returns: ['Hide Activities', 'Other', 'Modify Application Data']

info = fetcher.get_cwe_info('CWE-354')
# Returns: {
#   'id': 'CWE-354',
#   'name': 'Improper Validation of Integrity Check Value',
#   'description': 'The product does not validate...',
#   'technical_impacts': ['Hide Activities', 'Other', 'Modify Application Data']
# }
```

### Test Results

- **46 CWE fetcher tests** (13 new API-specific tests)
- **304 total backend tests** passing

## Files Modified

| File | Changes |
|------|---------|
| `src/data/loaders/cwe_fetcher.py` | Replaced XML with REST API |
| `src/data/loaders/trivy_loader.py` | Fixed NVDFetcher argument |
| `tests/test_cwe_fetcher.py` | Added API parsing tests |
| `.gitignore` | Added `src/data/cache/` |

## Commit

```
3c54d95 refactor(loaders): use CWE REST API instead of XML download
```

## Benefits

1. **No large download** - No 30MB XML ZIP to fetch
2. **Faster lookups** - Simple HTTP GET vs XML parsing
3. **Simpler code** - JSON parsing vs ElementTree
4. **Official API** - MITRE-supported, no auth required
5. **Better caching** - Separate info_cache for name/description

## Limitations

- Batch endpoint (`/cwe/74,79`) only returns minimal data (ID, Type)
- For full details including CommonConsequences, individual calls required
- No rate limiting documented, but should be respectful of API usage

## Next Steps (Optional)

- Implement multi-TI support in graph builder (CWE → multiple TI nodes)
- Currently only primary (first) TI is used per CWE
