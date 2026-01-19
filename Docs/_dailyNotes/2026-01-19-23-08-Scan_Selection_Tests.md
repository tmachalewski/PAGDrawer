# 2026-01-19 23:08 - Scan Selection Tests Implementation

## Overview

Added comprehensive backend API tests and frontend E2E tests for the scan selection feature implemented earlier today.

---

## Tests Implemented

### Backend API Tests (`tests/test_api_endpoints.py`)

Added `TestScanSelectionEndpoints` class with 8 tests:

| Test                                  | Description                                        |
| ------------------------------------- | -------------------------------------------------- |
| `test_list_scans_empty`               | Verify empty list when no scans uploaded           |
| `test_list_scans_after_upload`        | Verify scan metadata returned after upload         |
| `test_list_scans_multiple_uploads`    | Each scan gets unique UUID                         |
| `test_delete_scan`                    | Delete specific scan by ID                         |
| `test_delete_nonexistent_scan`        | 404 for invalid scan ID                            |
| `test_rebuild_with_specific_scan_ids` | Rebuild uses only selected scans                   |
| `test_rebuild_with_invalid_scan_ids`  | 400 error for non-matching IDs                     |
| `test_upload_returns_scan_metadata`   | Upload response includes scan_id, name, vuln_count |

### Frontend E2E Tests (`tests/test_frontend.py`)

Added `TestScanSelection` class with 8 Playwright tests:

| Test                                      | Description                            |
| ----------------------------------------- | -------------------------------------- |
| `test_data_source_section_exists`         | Data Source panel visible in sidebar   |
| `test_upload_button_exists`               | Upload Trivy Scan button visible       |
| `test_rebuild_button_exists`              | Rebuild button visible                 |
| `test_reset_button_exists`                | Reset button visible                   |
| `test_scan_selector_hidden_when_no_scans` | Selector hidden until scans uploaded   |
| `test_visibility_persists_after_rebuild`  | Hidden types stay hidden after rebuild |
| `test_enrich_checkbox_exists`             | Enrich from NVD/CWE checkbox visible   |
| `test_reset_returns_to_mock_data`         | Reset changes source to "mock"         |

---

## Bug Fixes During Testing

### 1. FastAPI Query Parameter for Lists

**Problem:** The `scan_ids` parameter was declared as `Optional[List[str]] = None`, which doesn't properly parse list values from query strings.

**Solution:** Changed to use FastAPI's `Query()`:
```python
# Before
scan_ids: Optional[List[str]] = None

# After
scan_ids: Optional[List[str]] = Query(default=None)
```

**Files Modified:** `src/viz/app.py` (lines 5, 392)

### 2. Test Fixture Reset

**Problem:** Test fixture was resetting `uploaded_trivy_data` which no longer exists (renamed to `uploaded_trivy_scans`).

**Solution:** Updated fixture:
```python
# Before
app_module.uploaded_trivy_data = []

# After
app_module.uploaded_trivy_scans = []
```

### 3. Frontend Locators

**Problem:** Initial tests used non-existent element IDs (`#upload-btn`, `#reset-btn`).

**Solution:** Updated to match actual HTML:
- `.upload-btn` (class selector)
- `.reset-btn` (class selector)
- `.stats-title` instead of `.panel-title`
- `#data-source` instead of `#data-source-status`

---

## Test Commands

```bash
# Run backend API tests
python -m pytest tests/test_api_endpoints.py::TestScanSelectionEndpoints -v

# Run frontend E2E tests (requires Vite + FastAPI running)
python -m pytest tests/test_frontend.py::TestScanSelection -v
```

---

## Test Results

```
tests/test_api_endpoints.py::TestScanSelectionEndpoints  8 passed in 0.51s
tests/test_frontend.py::TestScanSelection                8 passed in 14.91s
```

---

## Files Modified

| File                          | Changes                                                           |
| ----------------------------- | ----------------------------------------------------------------- |
| `src/viz/app.py`              | Added `Query` import, fixed `scan_ids` parameter                  |
| `tests/test_api_endpoints.py` | Added `TestScanSelectionEndpoints` class (8 tests), fixed fixture |
| `tests/test_frontend.py`      | Added `TestScanSelection` class (8 tests)                         |

---

## Commits

1. `feat: Add scan selection feature and fix visibility persistence` (3906fd3)
2. `test: Add backend and frontend tests for scan selection feature` (9803c17)
