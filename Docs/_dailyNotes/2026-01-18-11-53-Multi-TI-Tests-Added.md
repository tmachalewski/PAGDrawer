# Multi-TI Feature Tests Added

**Date:** 2026-01-18 11:53
**Status:** Completed
**Related:** 2026-01-18-11-25-Multi-TI-Feature-Implementation.md

## Overview

Added unit tests to verify the Multi-TI feature implementation where a single CWE can have multiple Technical Impact (TI) nodes.

## New Tests Added

### `tests/test_builder.py`

#### 1. `test_multiple_impacts_create_multiple_ti_nodes`

Verifies that multiple technical impacts create multiple TI nodes and edges.

```python
def test_multiple_impacts_create_multiple_ti_nodes(self, empty_graph_builder):
    """Multiple technical_impacts should create multiple TI nodes."""
    cwe_id = "CWE-78"
    empty_graph_builder.graph.add_node(cwe_id, node_type="CWE")

    # CWE-78 style: 4 different impacts
    impacts = [
        "Execute Unauthorized Code or Commands",
        "Read Files or Directories",
        "Modify Files or Directories",
        "Hide Activities"
    ]

    empty_graph_builder._wire_cwe_to_vcs(
        cwe_id,
        "host-001",
        "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        impacts,
        ""
    )

    stats = empty_graph_builder.get_stats()
    # Should have 4 TI nodes (one per impact)
    assert stats["node_counts"].get("TI", 0) == 4

    # Should have 4 HAS_IMPACT edges (CWE -> each TI)
    assert stats["edge_counts"].get("HAS_IMPACT", 0) == 4
```

**Asserts:**
- 4 impacts → 4 TI nodes
- 4 HAS_IMPACT edges (CWE → TI)

#### 2. `test_multiple_impacts_create_unique_ti_ids`

Verifies that each impact creates a unique TI node ID.

```python
def test_multiple_impacts_create_unique_ti_ids(self, empty_graph_builder):
    """Each impact should have a unique TI node ID."""
    cwe_id = "CWE-119"
    empty_graph_builder.graph.add_node(cwe_id, node_type="CWE")

    impacts = [
        "Execute Unauthorized Code or Commands",
        "Gain Privileges or Assume Identity",
        "Read Memory"
    ]

    empty_graph_builder._wire_cwe_to_vcs(
        cwe_id,
        "host-002",
        "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H",
        impacts,
        ""
    )

    # Get all TI node IDs
    ti_nodes = [
        node_id for node_id, data in empty_graph_builder.graph.nodes(data=True)
        if data.get("node_type") == "TI"
    ]

    # Should have 3 unique TI nodes
    assert len(ti_nodes) == 3
    assert len(set(ti_nodes)) == 3  # All unique
```

**Asserts:**
- 3 impacts → 3 TI nodes
- All TI node IDs are unique

## Complete Test Coverage

| Test | Coverage |
|------|----------|
| `test_skips_empty_technical_impacts` | Empty list → no TI nodes |
| `test_creates_ti_node_with_valid_impact` | Single impact → 1 TI node |
| `test_creates_vc_without_host_id` | Layer suffix handling |
| `test_multiple_impacts_create_multiple_ti_nodes` | N impacts → N TI nodes |
| `test_multiple_impacts_create_unique_ti_ids` | Unique TI IDs per impact |

## Test Results

```bash
python -m pytest tests/test_builder.py -v -k "WireCwe"
```

```
tests/test_builder.py::TestWireCweToVcs::test_skips_empty_technical_impacts PASSED
tests/test_builder.py::TestWireCweToVcs::test_creates_ti_node_with_valid_impact PASSED
tests/test_builder.py::TestWireCweToVcs::test_creates_vc_without_host_id PASSED
tests/test_builder.py::TestWireCweToVcs::test_multiple_impacts_create_multiple_ti_nodes PASSED
tests/test_builder.py::TestWireCweToVcs::test_multiple_impacts_create_unique_ti_ids PASSED

5 passed
```

## Scripts Created

Also created server management scripts in `Scripts/`:

| Script | Purpose |
|--------|---------|
| `start-backend.sh` | Start FastAPI on port 8000 |
| `start-frontend.sh` | Start Vite dev server |
| `kill-backend.sh` | Kill port 8000 processes |
| `kill-frontend.sh` | Kill port 3000/3001 processes |

Backend script uses: `python -m uvicorn src.viz.app:app --reload`
