# 2026-04-10 - Slider Granularity & Enrichment Preservation Fix

## Overview

Fixed three bugs related to the universality sliders in the Settings modal:
1. **TI/VC nodes disappeared** when changing the VC granularity slider
2. **ENABLES edges not created** at universal VC granularity levels
3. **Slider config not reset** when loading a new scan

Also added a Trivy scan example designed to showcase slider behavior.

---

## 1. Enrichment Data Lost on Config Change (Root Cause)

**Bug**: Moving any granularity slider caused all TI and VC nodes to vanish from the graph.

**Root cause**: The `/api/config` POST endpoint rebuilt the graph from raw Trivy JSON with `enrich=False` (line 164 in `app.py`). This discarded all CWE enrichment (technical impacts), so no TI or VC nodes were created after a slider change.

**Fix**: Cache the enriched `LoadedData` object after the initial rebuild. When sliders change, reuse the cached data instead of re-loading from raw Trivy JSON.

### Files Changed
- `src/viz/app.py` - Added `current_loaded_data` global cache, simplified config rebuild to reuse cached enriched data

---

## 2. ENABLES Edges Missing at Universal VC Granularity

**Bug**: When VC slider was at ATTACKER (universal), ENABLES edges were not created, leaving VC nodes orphaned.

**Root cause**: In `_wire_multistage_attacks()` (builder.py:627), VC nodes were indexed by `(vc_type, vc_value, host_id)`. Universal VC nodes have `host_id=None`, but the lookup used `cve["host_id"]` (e.g., `"host1"`). The key mismatch `("AV", "L", "host1")` vs `("AV", "L", None)` caused lookups to fail silently.

**Fix**: Added `vc_includes_host = self.config.should_include_context("VC", "HOST")` check. When VCs don't include host context, the lookup uses `None` as host_id.

### Files Changed
- `src/graph/builder.py` - Fixed VC lookup key in `_wire_multistage_attacks()`

---

## 3. Slider Config Not Reset on New Scan

**Bug**: Loading a new Trivy scan or resetting to mock data preserved the old slider configuration. Stale granularity settings persisted across different scans.

**Fix**:
- **Backend**: Reset `current_config` to `GraphConfig()` defaults in both `rebuild_from_uploaded_data()` and `reset_to_mock_data()` endpoints
- **Frontend**: Added `syncSlidersFromConfig()` function that fetches config from backend and updates slider positions. Called after rebuild and reset operations.

### Files Changed
- `src/viz/app.py` - Reset config in rebuild/reset endpoints, clear cached data on reset
- `frontend/js/ui/modal.ts` - Added exported `syncSlidersFromConfig()` function
- `frontend/js/features/dataSource.ts` - Call `syncSlidersFromConfig()` after rebuild and reset

---

## 4. Slider Showcase Trivy Scan

Created `examples/slider_showcase_trivy_scan.json` — a mocked Trivy scan with 5 vulnerabilities in a single host, designed to demonstrate slider behavior:

| CVE | Package | CWE | Leads to EX:Y? | CVSS |
|-----|---------|-----|----------------|------|
| CVE-2024-4741 | openssl | CWE-416 (Use After Free) | Yes | 9.8 CRITICAL |
| CVE-2024-2961 | musl | CWE-787 (OOB Write) | Yes | 9.8 CRITICAL |
| CVE-2024-5535 | openssl | CWE-125 (Buffer Overread) | No | 8.2 HIGH |
| CVE-2023-44487 | nghttp2-libs | CWE-400 (Resource Exhaustion) | No | 7.5 HIGH |
| CVE-2024-6119 | openssl | CWE-476 (NULL Deref) | No | 5.9 MEDIUM |

### Slider Showcase Properties
- **CPE slider**: 3 CVEs share `openssl` — merges at ATTACKER level
- **CWE slider**: CWE-416 and CWE-787 both produce "Execute Unauthorized Code" TI
- **VC slider**: Both EX:Y CVEs produce identical VC outcomes (AV:L, PR:H, EX:Y)
- **Environment filters**: CVE-2024-6119 has AC:H + UI:R, dimmed at default settings

---

## 5. New Tests

Added `TestVCGranularityEnablesEdges` class with 5 tests:

| Test | Verifies |
|------|----------|
| `test_vc_universal_still_has_enables_edges` | ENABLES edges exist at ATTACKER level |
| `test_vc_universal_fewer_nodes_than_singular` | Universal merges VC nodes |
| `test_vc_at_host_level_has_enables_edges` | ENABLES edges at HOST level |
| `test_vc_at_cve_level_has_enables_edges` | ENABLES edges at CVE level |
| `test_enables_count_consistent_across_granularities` | ENABLES edges at all 6 levels |

**Total test count**: 406 Python tests + 82 TypeScript tests = **488 total**

---

## Git Commits

```
bb5b488 fix: Preserve enrichment data when changing granularity sliders and reset config on rebuild
aa9946e docs: Add Trivy scan generation command reference
```

---

## Summary

| Area | Changes |
|------|---------|
| Bug fixes | 3 (enrichment cache, ENABLES edges, slider reset) |
| New example | slider_showcase_trivy_scan.json |
| New tests | +5 (TestVCGranularityEnablesEdges) |
| Files changed | 6 (builder.py, app.py, modal.ts, dataSource.ts, test_builder.py, example JSON) |
