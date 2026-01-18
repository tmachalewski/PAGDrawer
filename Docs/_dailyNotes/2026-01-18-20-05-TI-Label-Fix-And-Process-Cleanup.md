# TI Label Fix and Process Cleanup

**Date:** 2026-01-18 20:05
**Commit:** `c000dfc`

## Summary

Fixed TI (Technical Impact) node labels to show full names without truncation or CWE references.

## Problem

TI nodes displayed labels like:
```
Execute Unauthoriz...
(CWE-78)
```

Instead of the full technical impact name.

## Solution

### 1. Builder Changes (`src/graph/builder.py`)

**Before:**
```python
ti_short = technical_impact[:20] + "..." if len(technical_impact) > 20 else technical_impact
original_cwe = cwe_id.split("@")[0] if cwe_id else ""

if self.config.is_universal("TI"):
    ti_id = f"TI:{technical_impact[:20]}{layer_suffix}"
    ti_label = ti_short
elif self.config.should_include_context("TI", "CWE"):
    ti_id = f"TI:{technical_impact[:20]}@{cwe_id}"
    ti_label = f"{ti_short}\n({original_cwe})"
else:
    ti_id = f"TI:{technical_impact[:20]}@{host_id}"
    ti_label = f"{ti_short}\n({host_id[:15] if host_id else ''})"
```

**After:**
```python
ti_label = technical_impact

if self.config.is_universal("TI"):
    ti_id = f"TI:{technical_impact}{layer_suffix}"
elif self.config.should_include_context("TI", "CWE"):
    ti_id = f"TI:{technical_impact}@{cwe_id}"
else:
    ti_id = f"TI:{technical_impact}@{host_id}"
```

### 2. Result

TI labels now show full names:
- `Execute Unauthorized Code or Commands`
- `Read Files or Directories`
- `Modify Files or Directories`

## Debugging Issue: Stale Python Processes

### Problem

After code changes, the API still returned old truncated labels despite:
- Clearing `__pycache__`
- Restarting uvicorn server
- Multiple restart attempts

### Root Cause

Found 6 stale Python processes:
```
python.exe  18812
python.exe  24024
python.exe  25220
python.exe  26232
python.exe  10588
python.exe  12324
```

**Why they accumulated:**

1. **Uvicorn `--reload` architecture** - Spawns reloader + worker processes
2. **Old kill script only found port-bound processes** - Workers aren't bound to port
3. **Multiple restart attempts** - Each left more orphan workers

### Fix: Improved Kill Script

**Before (`Scripts/kill-backend.sh`):**
```bash
netstat -ano | grep ":8000" | awk '{print $5}' | sort -u | xargs -r -I {} taskkill //PID {} //F
```

**After:**
```bash
taskkill //F //IM python.exe 2>/dev/null
```

More aggressive but reliable for dev environments - kills all Python processes.

## Files Changed

| File | Change |
|------|--------|
| `src/graph/builder.py` | Remove label truncation and CWE suffix |
| `Scripts/kill-backend.sh` | Kill all Python processes on Windows |

## Lessons Learned

1. Uvicorn `--reload` creates process trees - killing parent doesn't kill children
2. On Windows, `taskkill //F //IM python.exe` is more reliable than port-based killing
3. When code changes don't take effect, check for stale processes with `tasklist | findstr python`
