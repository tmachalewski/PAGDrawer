# 2026-01-19 23:35 - VC Singularity Bug Fix (Long-Standing Issue)

## Overview

**FINALLY FIXED** the Vector Changer (VC) singularity configuration bug that has been plaguing the project. VCs now correctly respect the full context chain when set to singular mode.

---

## The Problem

When setting the VC slider in Settings to the most singular position (TI level), VCs **still appeared as universal** (single shared nodes like `VC:AV:N` and `VC:PR:L`) instead of being duplicated per-TI/CWE/CVE/CPE/HOST.

**Expected behavior**: 
- VC at ATTACKER level → Few shared nodes (e.g., `VC:AV:N`)
- VC at TI level → Many individual nodes (e.g., `VC:AV:N@TI:ExecCode@CWE-79@...`)

**Actual behavior before fix**:
- VC slider position had NO effect - always universal

---

## Root Cause Analysis

### The Broken Code

In `src/graph/builder.py`, the `_wire_cwe_to_vcs()` method had this logic:

```python
# OLD CODE (broken)
def _wire_cwe_to_vcs(self, cwe_id: str, host_id: str, cvss_vector: str, ...):
    ...
    # Determine VC ID based on host
    if host_id:
        vc_id = f"VC:{vc_type}:{vc_value}@{host_id}"
    else:
        vc_id = f"VC:{vc_type}:{vc_value}{layer_suffix}"  # ALWAYS UNIVERSAL!
```

### Why It Was Broken

1. **Only checked HOST context** - The method only received `host_id` parameter
2. **Missing CPE/CVE context** - No way to create per-CPE or per-CVE VCs
3. **Ignored TI context entirely** - Even though TI was the most singular level
4. **Call site passed None** when config didn't include HOST:
   ```python
   # Call site also broken
   self._wire_cwe_to_vcs(
       actual_cwe_id,
       host_id if self.config.should_include_context("VC", "HOST") else None,  # ← Only checked HOST!
       cve_data["cvss_vector"],
       ...
   )
   ```

---

## The Fix

### Updated Method Signature

```python
def _wire_cwe_to_vcs(
    self,
    cwe_id: str,
    host_id: Optional[str],       # Added Optional
    cpe_id: Optional[str],        # NEW PARAMETER
    cve_id: Optional[str],        # NEW PARAMETER
    cvss_vector: str,
    technical_impacts: List[str],
    layer_suffix: str = ""
):
```

### New VC ID Construction Logic

Now checks ALL levels from most specific to least:

```python
# NEW CODE (fixed)
# Determine VC ID based on config - check from most specific to least
if self.config.should_include_context("VC", "TI"):
    # Most granular: per-TI (VC inherits TI's full context)
    vc_id = f"VC:{vc_type}:{vc_value}@{ti_id}"
elif self.config.should_include_context("VC", "CWE") and cwe_id:
    vc_id = f"VC:{vc_type}:{vc_value}@{cwe_id}"
elif self.config.should_include_context("VC", "CVE") and cve_id:
    vc_id = f"VC:{vc_type}:{vc_value}@{cve_id}"
elif self.config.should_include_context("VC", "CPE") and cpe_id:
    vc_id = f"VC:{vc_type}:{vc_value}@{cpe_id}"
elif self.config.should_include_context("VC", "HOST") and host_id:
    vc_id = f"VC:{vc_type}:{vc_value}@{host_id}"
else:
    # Universal (ATTACKER level)
    vc_id = f"VC:{vc_type}:{vc_value}{layer_suffix}"
```

### Updated Call Site

```python
# Wire CWE -> VCs (pass full context for VC ID construction)
self._wire_cwe_to_vcs(
    actual_cwe_id,
    host_id if self.config.should_include_context("VC", "HOST") else None,
    actual_cpe_id if self.config.should_include_context("VC", "CPE") else None,  # NEW
    actual_cve_id if self.config.should_include_context("VC", "CVE") else None,  # NEW
    cve_data["cvss_vector"],
    cve_data.get("technical_impacts", []),
    layer_suffix
)
```

---

## VC Grouping Levels Reference

| Slider Position | Level    | VC ID Format        | Example                          |
| --------------- | -------- | ------------------- | -------------------------------- |
| Leftmost        | ATTACKER | `VC:{type}:{value}` | `VC:AV:N`                        |
| 2nd             | HOST     | `VC:...@{host_id}`  | `VC:AV:N@host-001`               |
| 3rd             | CPE      | `VC:...@{cpe_id}`   | `VC:AV:N@cpe:nginx:1.0@host-001` |
| 4th             | CVE      | `VC:...@{cve_id}`   | `VC:AV:N@CVE-2021-1234@cpe...`   |
| 5th             | CWE      | `VC:...@{cwe_id}`   | `VC:AV:N@CWE-79@CVE...`          |
| Rightmost       | TI       | `VC:...@{ti_id}`    | `VC:AV:N@TI:ExecCode@CWE...`     |

---

## Verification Results

### Browser Test

| Setting                   | Total Nodes | Change         |
| ------------------------- | ----------- | -------------- |
| VC @ ATTACKER (universal) | 247         | baseline       |
| VC @ TI (most singular)   | **451**     | **+204 nodes** |

The 204 additional nodes are VC nodes that are now correctly individualized per-TI context.

### Test Recording

![VC Singularity Test](file:///C:/Users/Tomek%20Machalewski/.gemini/antigravity/brain/497c1344-437c-47fa-a598-9aa1c117c322/vc_singularity_test_1768861893066.webp)

---

## Files Modified

| File                   | Changes                                                             |
| ---------------------- | ------------------------------------------------------------------- |
| `src/graph/builder.py` | Updated `_wire_cwe_to_vcs()` signature and VC ID construction logic |

---

## Commit

`e8f4d57` - "fix: VC singularity now respects full context chain (HOST/CPE/CVE/CWE/TI levels)"

---

## Why This Was Hard to Find

1. **Config system was correct** - `should_include_context()` worked fine
2. **Other node types worked** - CPE, CVE, CWE, TI all responded to sliders correctly
3. **VC method was isolated** - The bug was in a helper method, not the main flow
4. **Only affected VC** - All other singularity settings were wired correctly
5. **Subtle difference** - The method only used `host_id` instead of checking all levels

---

## Lessons Learned

1. **Follow the pattern** - Other node types (CPE, CVE, CWE, TI) use `should_include_context()` for each level, but VC only checked HOST
2. **Test all slider positions** - The bug was invisible until testing the full slider range
3. **Pass full context** - Helper methods need all context IDs to make proper decisions
