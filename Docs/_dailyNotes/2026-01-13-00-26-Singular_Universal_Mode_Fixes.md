# Singular/Universal Mode Fixes & Verification
**Date:** 2026-01-13 00:26

## Summary
Fixed and verified the singular/universal configuration mode for all node types (CPE, CVE, CWE, TI, VC) in the Settings modal.

---

## Problem
Settings modal options for "singular" vs "universal" node modes were not working correctly. The backend `builder.py` was hardcoding node IDs regardless of config.

---

## Fixes Applied

### Graph Builder (`src/graph/builder.py`)
Modified `_build_layer()` to respect `self.config.is_singular()`:

| Node Type | Singular ID Format                  | Universal ID Format               |
| --------- | ----------------------------------- | --------------------------------- |
| **CPE**   | `{cpe_id}@{host_id}`                | `{cpe_id}{layer_suffix}`          |
| **CVE**   | `{cve_id}@{actual_cpe_id}`          | `{cve_id}{layer_suffix}`          |
| **CWE**   | `{original_cwe_id}@{actual_cve_id}` | `{original_cwe_id}{layer_suffix}` |
| **TI**    | `TI:{impact[:20]}@{cwe_id}`         | `TI:{impact[:20]}{layer_suffix}`  |
| **VC**    | `{vc_type}:{value}@{host_id}`       | `{vc_type}:{value}{layer_suffix}` |

### Key Changes
- Added `if not self.graph.has_node(id)` checks to prevent duplicates in universal mode
- Added `if not self.graph.has_edge(source, target)` checks for edge deduplication
- Set `host_id` attribute to `None` for universal nodes
- Updated `_wire_cwe_to_vcs()` to handle TI and VC modes independently

---

## Verification Results

### TI Mode Test
| Mode      | TI Nodes | Example ID                                        |
| --------- | -------- | ------------------------------------------------- |
| Universal | 6        | `TI:Execute Unauthorized`                         |
| Singular  | 32       | `TI:Execute Unauthorized@CWE-22@CVE-...@host-001` |

### CVE Mode Test
| Mode      | Total Nodes |
| --------- | ----------- |
| Singular  | 175         |
| Universal | 151         |

---

## ENABLES Edges Investigation
Verified that `ENABLES` edges are NOT self-loops but legitimate multi-stage attack paths:

| Source VC          | Target CVE       | Producer CVEs                      |
| ------------------ | ---------------- | ---------------------------------- |
| `VC:AV:L@host-001` | `CVE-2021-3156`  | `CVE-2021-41773`, `CVE-2021-44228` |
| `VC:AV:L@host-002` | `CVE-2021-22555` | `CVE-2020-25213`                   |

Attack chain example:
```
CVE-2021-44228 (Remote) → VC:AV:L → CVE-2021-3156 (PrivEsc) → VC:PR:H → EX:Y
```

---

## Browser Testing
Used browser subagent with JavaScript execution to confirm:
- Frontend correctly sends config values to `/api/config`
- Backend rebuilds graph with correct node sharing
- Node counts change dynamically based on mode selection

---

## Test Status

| Test Suite         | Count   | Status     |
| ------------------ | ------- | ---------- |
| Python Backend     | 66      | ✅ Pass     |
| TypeScript Unit    | 9       | ✅ Pass     |
| Playwright Browser | 33      | ✅ Pass     |
| **Total**          | **108** | ✅ All Pass |

---

## Files Modified
- `src/graph/builder.py` - Lines 365-460 (node ID generation)
