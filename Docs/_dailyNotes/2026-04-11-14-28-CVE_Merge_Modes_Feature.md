# 2026-04-11 - CVE Merge Modes Feature

## Overview

Major feature addition: CVE node merging via Cytoscape compound nodes. When CWE and TI nodes are hidden, CVE nodes can be grouped by shared prerequisites or outcomes, reducing visual clutter and revealing structural patterns in the attack graph.

---

## 1. CVE Merge Modes

**Goal**: When intermediate nodes (CWE, TI) are hidden, many CVE nodes share identical CVSS prerequisites or produce the same VC outcomes. Merging them into compound boxes declutters the graph.

### Two Merge Strategies

| Mode | Grouping Key | Use Case |
|------|-------------|----------|
| **By Prerequisites** | AV/AC/PR/UI from CVSS vector | "Which CVEs need the same entry conditions?" |
| **By Outcomes** | VC outcomes produced (via CWE→TI→VC chain) | "Which CVEs produce the same privilege changes?" |

### Key Design Decisions

- **Layer-aware**: Merge keys include `layer` (L1/L2) and `chain_depth` to prevent cross-layer or cross-depth grouping
- **Compound nodes**: CVE_GROUP is a Cytoscape compound parent — children remain hoverable for tooltip inspection
- **Edge consolidation in outcomes mode**: Individual CVE→VC edges are hidden and replaced by deduped synthetic edges from the compound parent, reducing edge count by ~50%
- **Prereqs mode keeps individual edges**: Since CVEs in a prereqs group may connect to different VCs, edges stay on individual nodes

---

## 2. Backend Changes (builder.py)

### prereqs attribute on CVE nodes
Parses CVSS vector string into a `prereqs` dict `{AV, AC, PR, UI}` stored on each CVE node. Used by frontend for prereqs merge key computation.

### vc_outcomes attribute on CVE nodes
After building each CVE's CWE→TI→VC chain, collects all `(vc_type, vc_value)` pairs into a sorted `vc_outcomes` list on the CVE node. Used by frontend for outcomes merge key.

### GEXF export fix
`prereqs` (dict) and `vc_outcomes` (list of lists) caused `ValueError` in NetworkX GEXF serializer. Fixed by stripping non-serializable attributes from a graph copy before export.

### Files Changed
- `src/graph/builder.py` — Added prereqs parsing, vc_outcomes storage, GEXF export cleanup

---

## 3. Frontend Implementation

### New Module: `frontend/js/features/cveMerge.ts` (~310 lines)

Core merge logic with dependency injection to avoid circular imports with `filter.ts`.

| Export | Purpose |
|--------|---------|
| `isMergeAvailable()` | Returns true when CWE+TI both hidden |
| `computePrereqKey(node)` | Key from CVSS prereqs + layer + depth |
| `computeOutcomeKey(node)` | Key from vc_outcomes + layer + depth |
| `formatMergeLabel(key, count, mode)` | Human-readable compound label |
| `setMergeMode(mode)` | Applies/removes merge, updates UI |
| `applyMerge()` | Creates compound parents, reparents CVEs, consolidates edges (outcomes) |
| `removeMerge()` | Dissolves compounds, restores edges |
| `resetMerge()` | Resets state on graph rebuild |
| `setupMergeButton()` | Wires button and popover event handlers |
| `injectGetHiddenTypes(fn)` | Breaks circular dependency with filter.ts |

### Circular Dependency Resolution
`filter.ts` imports from `cveMerge.ts` (to update button on visibility changes), and `cveMerge.ts` needs `getHiddenTypes` from `filter.ts`. Solved via dependency injection: `main.ts` calls `injectGetHiddenTypes(getHiddenTypes)` during init.

### UI Components

- **Merge button** (`⊞`): Always visible, greyed out/disabled when CWE+TI not hidden, with tooltip hint
- **Popover menu**: Three options — No Merge, By Prerequisites, By Outcomes
- **Toast notification**: One-time notification when merge first becomes available
- **CVE_GROUP style**: Dashed yellow border, semi-transparent background, top-aligned label

### Edge Consolidation (Outcomes Mode)

In outcomes mode, all CVEs in a group connect to the same VCs. Instead of N×M edges:
1. Original edges hidden via `display: none`
2. Deduped synthetic edges created from compound parent
3. Edges restored on merge removal

### Files Changed
- `frontend/js/features/cveMerge.ts` — New module
- `frontend/js/features/cveMerge.test.ts` — 36 tests
- `frontend/js/features/filter.ts` — Wired `updateMergeButtonVisibility()` calls
- `frontend/js/ui/modal.ts` — Added `resetMerge()` on settings save
- `frontend/js/main.ts` — Imports, dependency injection, setup
- `frontend/js/config/constants.ts` — CVE_GROUP node style
- `frontend/index.html` — Merge button and popover HTML
- `frontend/css/styles.css` — Merge button, popover, toast, disabled state styles

---

## 4. Backend Tests

### `tests/test_builder.py` — `TestCVEMergeAttributes` (6 tests)
- `test_cve_has_prereqs_attribute` — prereqs dict exists on CVE nodes
- `test_prereqs_match_cvss_vector` — values match parsed CVSS
- `test_cve_has_vc_outcomes_attribute` — vc_outcomes list exists
- `test_vc_outcomes_match_actual_vc_chain` — outcomes match actual TI→VC chain
- `test_vc_outcomes_sorted` — outcomes are deterministically sorted
- `test_prereqs_consistent_across_duplicate_cve_nodes` — same CVE on different hosts has same prereqs

---

## 5. Frontend Tests

### `frontend/js/features/cveMerge.test.ts` (36 tests)

| Describe Block | Count | Coverage |
|---------------|-------|----------|
| `isMergeAvailable` | 6 | All combinations of hidden types |
| `computePrereqKey` | 7 | Keys, depth, layer separation, grouping |
| `computeOutcomeKey` | 6 | Keys, depth, layer separation, empty outcomes |
| `formatMergeLabel` | 4 | Prereqs format, outcomes format, depth/layer stripping |
| `getMergeMode` | 1 | Default state |
| `setMergeMode` | 4 | Mode updates, button classes, popover state |
| `applyMerge/removeMerge` | 7 | Compound creation, reparenting, edge consolidation, singletons, outcomes |
| `resetMerge` | 1 | State reset |

---

## 6. Key Bug: Cross-Layer Merging

**Problem**: Same CVEs appear on both L1 (getting foothold) and L2 (internal network) with identical prereqs and chain_depth=0. Without layer discrimination, all 10 CVEs merged into one huge compound spanning both layers.

**Fix**: Added `layer` (L1/L2) to merge key computation. `AV:N|AC:L|PR:N|UI:N|L1|d0` and `AV:N|AC:L|PR:N|UI:N|L2|d0` are now separate groups.

---

## 7. Evolution of Approach

The implementation went through three iterations:

1. **Compound parents (initial)** — CVEs reparented into compound nodes. Worked but produced huge yellow rectangles because dagre positioned children based on graph topology.
2. **Collapsed representative nodes** — CVEs hidden, single group node with synthetic edges. Compact but lost hover-over inspection of individual CVEs.
3. **Compound parents with layer separation (final)** — Back to compounds, but with layer-aware keys producing smaller, per-layer groups. User can hover individual CVEs inside the box. Edge consolidation in outcomes mode reduces visual clutter.
