# 2026-04-10 - Multi-CWE Support, Attack Chains & UI Fixes

## Overview

Major session focused on deepening the attack graph model with multi-CWE per CVE support, multi-stage attack chain improvements, and several UI fixes including per-node-type counts and tooltip re-initialization after Trivy uploads.

---

## 1. Multi-CWE per CVE

**Problem**: Each CVE was limited to a single CWE (`cwe_id` string field). Real vulnerabilities often map to multiple weakness categories (e.g., CVE-2024-3596 is both CWE-22 Path Traversal and CWE-287 Authentication Bypass).

**Solution**: Changed data model from `cwe_id: str` to `cwe_ids: list[str]` throughout the pipeline with full backwards compatibility.

### Files Changed
- `src/data/loaders/trivy_loader.py` - Iterate all `vuln.CweIDs` instead of taking `[0]`
- `src/data/loaders/nvd_fetcher.py` - Pass full `cwe_ids` list from NVD
- `src/data/loaders/base.py` - Validation accepts `cwe_ids` list or legacy `cwe_id`
- `src/graph/builder.py` - Loop over `cwe_ids` list, create CWE node + TI/VC chain per CWE
- `tests/test_trivy_loader.py` - Updated assertions for `cwe_ids`
- `tests/test_data_loaders.py` - Updated validation message

### Key Pattern (builder.py)
```python
original_cwe_ids = cve_data.get("cwe_ids", [])
if not original_cwe_ids and cve_data.get("cwe_id"):
    original_cwe_ids = [cve_data["cwe_id"]]  # backwards compat
for original_cwe_id in original_cwe_ids:
    cwe_technical_impacts = STATIC_CWE_MAPPING.get(original_cwe_id, [])
    # ... create CWE node, wire TI/VC per CWE
```

---

## 2. Multi-Stage Attack Chain Improvements

### Initial Attacker VC Nodes
Added UI:N and AC:L as initial VC nodes alongside existing AV:N and PR:N. These represent the attacker's starting capabilities (no user interaction needed, low complexity attacks available).

### ENABLES Edge Fix
**Bug**: `vc_nodes` dict in `_wire_multistage_attacks()` used `(type, value, host_id)` as key mapping to a single `node_id`. When multiple VCs had the same type/value/host but different TI/CWE context, only the last one was kept.

**Fix**: Changed from `dict[key] = node_id` to `dict.setdefault(key, []).append(node_id)` and lookups from `.append()` to `.extend()`.

### Local Privilege Escalation CVE
Added CVE-2022-2588 (AV:L/AC:L/PR:L/UI:N, CWE-416) to the slider showcase scan. This creates a multi-stage attack: attacker gains AV:L from exploiting an initial CVE, which then ENABLES exploitation of CVE-2022-2588 (requires local access).

### Subnet ID Fix
Changed default `subnet_id` from `"default"` to `"dmz"` in trivy_loader.py so that attacker CAN_REACH edges connect properly to hosts.

---

## 3. Per-Node-Type Counts in Settings Modal

Added live count badges next to each slider label showing how many visible nodes of that type exist.

### Files Changed
- `frontend/index.html` - Added `<span class="slider-count" id="count-{TYPE}">` elements
- `frontend/js/ui/sidebar.ts` - Count visible nodes per type in `updateLiveStats()`
- `frontend/css/styles.css` - `.slider-count` styling (green, 10px)

---

## 4. Tooltip Fix After Trivy Upload

**Problem**: Tooltips stopped working after uploading a Trivy scan and rebuilding the graph.

**Root cause**: `dataSource.ts` wasn't properly tearing down and reinitializing graph event handlers after rebuild. It was missing calls to `destroyCytoscape()`, `setupEventHandlers()`, `setupTooltip()`, `clearSelectedNode()`, `clearHiddenElements()`, and `applyEnvironmentFilter()`.

**Fix**: Both `rebuildGraph()` and `resetToMock()` now follow the same teardown/init pattern as `modal.ts`'s `saveSettings()`.

---

## 5. Dev Server Configuration

Created `.claude/launch.json` with configurations for Backend (FastAPI/uvicorn) and Frontend (Vite).

---

## Summary of All Changes

| Area | Change |
|------|--------|
| Data model | `cwe_id` -> `cwe_ids` (list) with backwards compat |
| Builder | Per-CWE TI/VC chain creation, ENABLES dict fix |
| Attacker | Added UI:N, AC:L initial VCs |
| Connectivity | Default subnet_id changed to "dmz" |
| UI | Per-type node counts in settings sliders |
| UI | Tooltip re-init after Trivy upload/rebuild |
| Example data | Added CVE-2024-3596 (2 CWEs), CVE-2022-2588 (AV:L) |
| Config | `.claude/launch.json` for dev servers |
