# Granular Grouping Sliders

**Date:** 2026-01-16
**Status:** Completed

---

## Summary

Implemented granular grouping control for node types in the Settings modal. Replaced binary singular/universal dropdowns with multi-position sliders that allow fine-grained control over how nodes are grouped.

---

## Background

Previously, each node type could only be set to:
- **universal**: One shared node globally
- **singular**: Duplicated per immediate parent

This limited flexibility - for example, TI (Technical Impact) could only be shared globally OR duplicated per-CWE, with no middle ground.

---

## New Feature: Granular Grouping Sliders

### UI Changes

Each node type now has a slider with options based on the attack chain hierarchy:

| Node Type | Slider Options |
|-----------|----------------|
| CPE | ATTACKER, HOST |
| CVE | ATTACKER, HOST, CPE |
| CWE | ATTACKER, HOST, CPE, CVE |
| TI | ATTACKER, HOST, CPE, CVE, CWE |
| VC | ATTACKER, HOST, CPE, CVE, CWE, TI |

Sliders are aligned vertically so the same grouping level (e.g., "CPE") appears at the same column position across all node types.

### Backend Changes (`src/core/config.py`)

- Extended `DuplicationMode` to accept: `"ATTACKER"`, `"HOST"`, `"CPE"`, `"CVE"`, `"CWE"`, `"TI"`
- Added `GROUPING_HIERARCHY` constant defining the node type order
- Added `VALID_GROUPINGS` mapping valid grouping levels for each node type
- New methods:
  - `get_grouping_level()` - returns the grouping level for a node type
  - `should_include_context()` - determines if a parent's ID should be included in node IDs
- Backward compatible with legacy `"singular"`/`"universal"` values

### Builder Changes (`src/graph/builder.py`)

Updated node ID generation to use `should_include_context()`:
- CPE: can include HOST context
- CVE: can include HOST and/or CPE context
- CWE: can include HOST, CPE, and/or CVE context
- TI: can include HOST through CWE context
- VC: can include HOST through TI context

### Frontend Changes

**`frontend/index.html`:**
- Replaced dropdown selects with range sliders
- Added column header row showing grouping options
- Each slider spans only the columns relevant to that node type

**`frontend/css/styles.css`:**
- Grid-based layout for aligned columns
- Slider styling with gradient (purple to green)

**`frontend/js/ui/modal.ts`:**
- `sliderPositionToConfig()` returns actual grouping level (e.g., "HOST")
- `configToSliderPosition()` converts config values to slider positions
- Backward compatible with legacy values

---

## Example

Setting TI slider to position 2 (CPE):
- Config value stored: `"CPE"`
- Effect: TI nodes are grouped per-CPE (shared across CVEs on the same software)
- Node IDs include host_id and cpe_id, but not cve_id or cwe_id

---

## Files Changed

```
src/core/config.py        - Extended DuplicationMode, new helper methods
src/graph/builder.py      - Updated node ID generation logic
frontend/index.html       - Slider HTML structure
frontend/css/styles.css   - Grid layout and slider styling
frontend/js/ui/modal.ts   - Slider value conversion logic
tests/test_config.py      - Updated tests for new format
tests/test_api.py         - Updated config endpoint test
```

---

## Testing

All 146 tests pass:
- Backend tests verify new config methods
- E2E tests verify slider UI functionality
- Slider positions now persist correctly after save

---

## Technical Notes

The grouping hierarchy follows the attack chain:
```
ATTACKER → HOST → CPE → CVE → CWE → TI → VC
```

Each node type can only be grouped by ancestors in this chain. "ATTACKER" grouping means universal (shared globally), while grouping by the immediate predecessor means most granular (per-parent).
