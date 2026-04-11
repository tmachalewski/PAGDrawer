# CVE Merge Modes — Detailed Implementation Plan

**Date:** 2026-04-11
**Branch:** `feature/cve-merge-modes`
**Status:** Planning

---

## 1. Problem Statement

When many CVEs share the same CVSS prerequisites (AV/AC/UI/PR) or produce the same downstream VCs, the graph contains structurally identical chains that clutter the visualization without adding information. Users need a way to visually group these equivalent CVEs to reveal patterns like "12 CVEs all require AV:N/PR:N" or "these 5 CVEs all produce AV:L + PR:H."

### Two merge strategies

| Strategy | Groups by | Label example | Use case |
|----------|-----------|---------------|----------|
| **By Prerequisites** | Identical (AV, AC, UI, PR) tuple from CVSS vector | `AV:N/PR:N (×6)` | "Which CVEs need the same access?" |
| **By Outcomes** | Identical set of (vc_type, vc_value) pairs produced | `AV:L, PR:H, EX:Y (×3)` | "Which CVEs grant the same capabilities?" |

---

## 2. Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Merge is a **frontend-only visual grouping** using Cytoscape compound (parent) nodes | Original graph data untouched; easily reversible; no backend rebuild needed |
| 2 | Merge controls placed on the **CVE sidebar row** as a `⊞` button | Spatially close to CVE type; naturally tied to CVE visibility |
| 3 | Merge only available when **CWE + TI are both hidden** | With downstream chains visible, compound grouping creates overlapping visual mess |
| 4 | VC visibility is **independent** of merge | VCs connect to CVEs upstream (ENABLES) or downstream (bridge); both work with compounds |
| 5 | When CWE or TI is re-shown, **merge auto-disables** | Prevents invalid visual state without user needing to manually un-merge first |
| 6 | Merge mode **not persisted** to backend config | Pure view concern — resets on graph rebuild, page reload |
| 7 | Chain depth `dN` is **part of the merge key** | CVEs at depth 0 and depth 1 with same prereqs are different attack stages — must not merge |
| 8 | Backend stores `prereqs` and `vc_outcomes` **on CVE nodes** | Frontend can compute merge keys without traversing hidden CWE→TI→VC chains |

---

## 3. UI Design

### 3.1 Sidebar Legend — CVE Row

**Current HTML** (`index.html:109-115`):
```html
<div class="node-type-row">
    <button class="filter-btn legend-filter-btn" data-type="CVE">
        <div class="legend-dot" style="background: #eab308;"></div>
        <span>CVE</span>
    </button>
    <button class="visibility-toggle" data-type="CVE" title="Hide/Show CVE nodes">👁</button>
</div>
```

**New HTML** — add merge button:
```html
<div class="node-type-row">
    <button class="filter-btn legend-filter-btn" data-type="CVE">
        <div class="legend-dot" style="background: #eab308;"></div>
        <span>CVE</span>
    </button>
    <button class="visibility-toggle" data-type="CVE" title="Hide/Show CVE nodes">👁</button>
    <button class="merge-toggle" id="cve-merge-btn" title="Merge CVE nodes"
            style="display: none;">⊞</button>
</div>
```

### 3.2 Merge Popover

Positioned relative to the `⊞` button, appears on click:

```html
<div id="merge-popover" class="merge-popover" style="display: none;">
    <div class="merge-option active" data-mode="none">No Merge</div>
    <div class="merge-option" data-mode="prereqs">By Prerequisites (AV/AC/UI/PR)</div>
    <div class="merge-option" data-mode="outcomes">By Outcomes (same VCs)</div>
</div>
```

### 3.3 Toast Notification

When the user hides both CWE and TI (whichever is hidden second triggers it), a **toast message** appears briefly at the bottom of the screen:

> "CVE merging now available — click ⊞ on CVE row"

**Toast behavior:**
- Appears for ~4 seconds, then fades out
- Shown only **once per session** (tracked via a `toastShown` flag) — not on every hide/show cycle
- Dismissed early by clicking
- Styled as a subtle info bar, not an intrusive alert

**HTML** — appended to `<body>` dynamically (no static HTML needed):
```html
<div id="merge-toast" class="merge-toast">
    CVE merging now available — click ⊞ on CVE row
</div>
```

**CSS:**
```css
.merge-toast {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(234, 179, 8, 0.9);
    color: #000;
    padding: 10px 24px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    z-index: 10000;
    opacity: 0;
    transition: opacity 0.3s;
    pointer-events: auto;
    cursor: pointer;
}
.merge-toast.visible {
    opacity: 1;
}
```

### 3.4 Interaction Flow

```
User hides CWE (via 👁)  ─┐
User hides TI  (via 👁)  ─┼─→  ⊞ button appears on CVE row
                           │     + toast: "CVE merging now available" (once)
                           │
User clicks ⊞            ─→  Popover opens with 3 options
User selects "By Prereqs" ─→  Compound nodes created, popover closes, ⊞ glows
User clicks ⊞ again       ─→  Popover opens, "By Prereqs" highlighted
User selects "No Merge"   ─→  Compounds dissolved, ⊞ glow removed
User shows CWE (via 👁)   ─→  Merge auto-disabled, ⊞ hides
```

### 3.4 CSS Styling

```css
/* Merge toggle button */
.merge-toggle {
    background: none;
    border: 1px solid rgba(234, 179, 8, 0.3);  /* CVE yellow, subtle */
    color: #eab308;
    cursor: pointer;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 14px;
    transition: all 0.2s;
}
.merge-toggle:hover {
    background: rgba(234, 179, 8, 0.15);
}
.merge-toggle.active {
    background: rgba(234, 179, 8, 0.25);
    border-color: #eab308;
    box-shadow: 0 0 6px rgba(234, 179, 8, 0.4);
}

/* Popover dropdown */
.merge-popover {
    position: absolute;
    background: #1e1e2e;
    border: 1px solid rgba(234, 179, 8, 0.4);
    border-radius: 8px;
    padding: 4px 0;
    z-index: 1000;
    min-width: 220px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.5);
}
.merge-option {
    padding: 8px 16px;
    cursor: pointer;
    font-size: 12px;
    color: #ccc;
    transition: background 0.15s;
}
.merge-option:hover {
    background: rgba(234, 179, 8, 0.15);
}
.merge-option.active {
    color: #eab308;
    font-weight: bold;
}
```

Light theme variants needed in `.light-theme` section.

---

## 4. Cytoscape Compound Node Style

**File:** `frontend/js/config/constants.ts` — add after existing compound style (`node[?is_compound]`):

```typescript
{
    selector: '[type="CVE_GROUP"]',
    style: {
        'background-color': 'rgba(234, 179, 8, 0.12)',
        'border-color': '#eab308',
        'border-width': 2,
        'border-style': 'dashed',
        'label': 'data(label)',
        'text-valign': 'top',
        'text-halign': 'center',
        'font-size': '10px',
        'color': '#eab308',
        'text-outline-color': '#000000',
        'text-outline-width': 1,
        'padding': '12px',
        'shape': 'round-rectangle'
    }
}
```

**Edge behavior**: Cytoscape automatically clips edges to compound node boundaries when children have edges. No edge rewiring needed — edges to/from child CVEs visually route to the compound boundary.

---

## 5. Backend Changes

### 5.1 Store prerequisites on CVE nodes

**File:** `src/graph/builder.py`, method `_build_cve_chain()` (line ~660)

Currently the CVE node is created at line 658-670. After `self.graph.add_node(...)`, the prerequisites can be extracted from the already-stored `cvss_vector` — but to avoid the frontend needing to parse CVSS strings, store parsed prereqs explicitly.

**Where to add** — immediately after the `self.graph.add_node(actual_cve_id, ...)` block (line 670), and before the CWE processing loop:

```python
# Store parsed prerequisites for frontend merge-by-prereqs
from src.core.consensual_matrix import extract_prerequisites as _extract_prereqs
_prereq_list = _extract_prereqs(cve_data["cvss_vector"])
# Include AC and UI from CVSS for complete prerequisite picture
_cvss_parts = {}
for part in (cve_data["cvss_vector"] or "").split("/"):
    if ":" in part:
        k, v = part.split(":", 1)
        _cvss_parts[k] = v
_full_prereqs = {
    "AV": _cvss_parts.get("AV", "N"),
    "AC": _cvss_parts.get("AC", "L"),
    "PR": _cvss_parts.get("PR", "N"),
    "UI": _cvss_parts.get("UI", "N"),
}
self.graph.nodes[actual_cve_id]["prereqs"] = _full_prereqs
```

**Why a dict instead of list of tuples**: JSON serialization converts tuples to arrays; a flat dict `{"AV":"N","AC":"L","PR":"N","UI":"N"}` is simpler for the frontend to consume and produces a clean merge key.

### 5.2 Store VC outcomes on CVE nodes

**Where to add** — at the end of `_build_cve_chain()`, after the CWE loop completes and `all_vc_info` is fully populated (line ~728, before the `return`):

```python
# Store VC outcomes for frontend merge-by-outcomes
vc_outcomes = sorted(set((vt, vv) for vt, vv, _ in all_vc_info))
# Convert to serializable format: [["AV","L"], ["EX","Y"], ["PR","H"]]
self.graph.nodes[actual_cve_id]["vc_outcomes"] = [list(pair) for pair in vc_outcomes]
```

### 5.3 Data flow through API

`to_json()` (line 1015) spreads `**data` from each node, so `prereqs` and `vc_outcomes` pass through automatically.

`app.py` line 103 does `**{k: v for k, v in node.items() if k not in ["id", "node_type"]}`, which also passes them through.

The frontend receives CVE node data like:
```json
{
    "id": "CVE-2024-4741:d0@cpe:...",
    "label": "CVE-2024-4741",
    "type": "CVE",
    "prereqs": {"AV": "N", "AC": "L", "PR": "N", "UI": "N"},
    "vc_outcomes": [["AV", "L"], ["EX", "Y"], ["PR", "H"]],
    "chain_depth": 0,
    "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    ...
}
```

No API endpoint changes needed.

---

## 6. Frontend — New Module `cveMerge.ts`

### 6.1 File: `frontend/js/features/cveMerge.ts`

```typescript
/**
 * CVE node merging via Cytoscape compound (parent) nodes.
 *
 * Groups CVE nodes by prerequisites or outcomes when CWE+TI are hidden.
 * Merge is purely visual — original node identity preserved as children
 * of compound parent nodes.
 */

import { getCy } from '../graph/core';
import { getHiddenTypes } from './filter';

export type MergeMode = 'none' | 'prereqs' | 'outcomes';

// --- State ---
let currentMergeMode: MergeMode = 'none';
let mergeParentIds: string[] = [];  // IDs of created compound parent nodes
```

### 6.2 Key functions

#### `isMergeAvailable(): boolean`

```typescript
export function isMergeAvailable(): boolean {
    const hidden = getHiddenTypes();
    return hidden.has('CWE') && hidden.has('TI');
}
```

#### `updateMergeButtonVisibility(): void`

```typescript
let toastShown = false;  // only show toast once per session

export function updateMergeButtonVisibility(): void {
    const btn = document.getElementById('cve-merge-btn');
    if (!btn) return;

    const wasHidden = btn.style.display === 'none';

    if (isMergeAvailable()) {
        btn.style.display = '';  // show

        // Show toast the first time merge becomes available
        if (wasHidden && !toastShown) {
            toastShown = true;
            showMergeToast();
        }
    } else {
        btn.style.display = 'none';  // hide
        // Auto-disable merge if conditions no longer met
        if (currentMergeMode !== 'none') {
            setMergeMode('none');
        }
    }
}

function showMergeToast(): void {
    const toast = document.createElement('div');
    toast.className = 'merge-toast';
    toast.textContent = 'CVE merging now available — click ⊞ on CVE row';
    document.body.appendChild(toast);

    // Fade in
    requestAnimationFrame(() => toast.classList.add('visible'));

    // Dismiss on click or after 4 seconds
    const dismiss = () => {
        toast.classList.remove('visible');
        setTimeout(() => toast.remove(), 300);
    };
    toast.addEventListener('click', dismiss);
    setTimeout(dismiss, 4000);
}
```
```

#### `setMergeMode(mode: MergeMode): void`

```typescript
export function setMergeMode(mode: MergeMode): void {
    currentMergeMode = mode;

    if (mode === 'none') {
        removeMerge();
    } else {
        applyMerge();
    }

    // Update button active state
    const btn = document.getElementById('cve-merge-btn');
    if (btn) {
        btn.classList.toggle('active', mode !== 'none');
    }

    // Update popover active option
    document.querySelectorAll('.merge-option').forEach(opt => {
        const el = opt as HTMLElement;
        el.classList.toggle('active', el.dataset.mode === mode);
    });
}
```

#### `computePrereqKey(node): string`

```typescript
function computePrereqKey(node: any): string {
    const prereqs = node.data('prereqs');
    const depth = node.data('chain_depth') ?? 0;
    if (!prereqs) return `unknown:d${depth}`;

    // prereqs is {AV: "N", AC: "L", PR: "N", UI: "N"}
    return `AV:${prereqs.AV}|AC:${prereqs.AC}|PR:${prereqs.PR}|UI:${prereqs.UI}|d${depth}`;
}
```

Chain depth is appended to prevent merging across attack stages.

#### `computeOutcomeKey(node): string`

```typescript
function computeOutcomeKey(node: any): string {
    const outcomes = node.data('vc_outcomes');
    const depth = node.data('chain_depth') ?? 0;
    if (!outcomes || !Array.isArray(outcomes)) return `unknown:d${depth}`;

    // outcomes is [["AV","L"], ["EX","Y"], ["PR","H"]]
    // Already sorted by backend
    const key = outcomes.map(([t, v]: [string, string]) => `${t}:${v}`).join(',');
    return `${key}|d${depth}`;
}
```

#### `applyMerge(): void`

```typescript
function applyMerge(): void {
    removeMerge();  // clean previous
    const cy = getCy();
    if (!cy || currentMergeMode === 'none') return;

    const cveNodes = cy.nodes('[type="CVE"]');
    const groups: Map<string, string[]> = new Map();

    // Group CVEs by computed key
    cveNodes.forEach(node => {
        const key = currentMergeMode === 'prereqs'
            ? computePrereqKey(node)
            : computeOutcomeKey(node);
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key)!.push(node.id());
    });

    // Create compound parent for each group with 2+ members
    groups.forEach((nodeIds, key) => {
        if (nodeIds.length < 2) return;

        const parentId = `cve_merge_${currentMergeMode}_${key}`;
        cy.add({
            group: 'nodes',
            data: {
                id: parentId,
                type: 'CVE_GROUP',
                label: formatMergeLabel(key, nodeIds.length),
                mergeKey: key,
                mergeMode: currentMergeMode
            }
        });
        mergeParentIds.push(parentId);

        // Move children into compound
        nodeIds.forEach(id => {
            cy.getElementById(id).move({ parent: parentId });
        });
    });
}
```

#### `formatMergeLabel(key, count): string`

```typescript
function formatMergeLabel(key: string, count: number): string {
    // Remove depth suffix for display
    const cleanKey = key.replace(/\|d\d+$/, '');

    if (currentMergeMode === 'prereqs') {
        // "AV:N|AC:L|PR:N|UI:N" → "AV:N / AC:L / PR:N / UI:N (×6)"
        return cleanKey.replace(/\|/g, ' / ') + ` (×${count})`;
    } else {
        // "AV:L,EX:Y,PR:H" → "→ AV:L, EX:Y, PR:H (×3)"
        return '→ ' + cleanKey.replace(/,/g, ', ') + ` (×${count})`;
    }
}
```

#### `removeMerge(): void`

```typescript
function removeMerge(): void {
    const cy = getCy();
    if (!cy) return;

    // Move children out of compound parents (back to root)
    mergeParentIds.forEach(parentId => {
        const parent = cy.getElementById(parentId);
        if (parent.length) {
            parent.children().move({ parent: null });
            parent.remove();
        }
    });
    mergeParentIds = [];
}
```

#### `setupMergeButton(): void`

```typescript
export function setupMergeButton(): void {
    const btn = document.getElementById('cve-merge-btn');
    if (!btn) return;

    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        togglePopover();
    });

    // Setup popover options
    document.querySelectorAll('.merge-option').forEach(opt => {
        opt.addEventListener('click', (e) => {
            e.stopPropagation();
            const mode = (opt as HTMLElement).dataset.mode as MergeMode;
            setMergeMode(mode);
            hidePopover();
        });
    });

    // Close popover on outside click
    document.addEventListener('click', () => hidePopover());
}

function togglePopover(): void {
    const popover = document.getElementById('merge-popover');
    if (!popover) return;

    if (popover.style.display === 'none') {
        // Position relative to merge button
        const btn = document.getElementById('cve-merge-btn');
        if (btn) {
            const rect = btn.getBoundingClientRect();
            popover.style.left = rect.left + 'px';
            popover.style.top = (rect.bottom + 4) + 'px';
        }
        popover.style.display = 'block';
    } else {
        popover.style.display = 'none';
    }
}

function hidePopover(): void {
    const popover = document.getElementById('merge-popover');
    if (popover) popover.style.display = 'none';
}
```

#### `resetMerge(): void`

Called on graph rebuild:

```typescript
export function resetMerge(): void {
    currentMergeMode = 'none';
    mergeParentIds = [];
    const btn = document.getElementById('cve-merge-btn');
    if (btn) btn.classList.remove('active');
    updateMergeButtonVisibility();
}
```

---

## 7. Integration Points

### 7.1 `filter.ts` — Wire visibility changes to merge

**Import** at top of `filter.ts`:
```typescript
import { updateMergeButtonVisibility, removeMerge } from './cveMerge';
```

**In `hideNodeType()`** — add at end (after `nodesToHide.remove()`):
```typescript
updateMergeButtonVisibility();
```

**In `showNodeType()`** — add at end (after `typesToRemainHidden.forEach(...)`):
```typescript
// Auto-disable merge if CWE or TI is being shown
if (type === 'CWE' || type === 'TI') {
    removeMerge();
}
updateMergeButtonVisibility();
```

**In `resetVisibility()`** — add at end:
```typescript
removeMerge();
updateMergeButtonVisibility();
```

**In `reapplyHiddenTypes()`** — add at end:
```typescript
updateMergeButtonVisibility();
```

### 7.2 `modal.ts` — Reset merge on graph rebuild

**Import** at top:
```typescript
import { resetMerge } from '../features/cveMerge';
```

**In `saveSettings()`** — add after `clearSelectedNode()` (line 179):
```typescript
resetMerge();
```

### 7.3 `main.ts` — Initialize merge button

**Import**:
```typescript
import { setupMergeButton } from './features/cveMerge';
```

**In `init()`** — add after `setupFilterButtons()`:
```typescript
setupMergeButton();
```

---

## 8. Edge Cases & Behavior Matrix

| Scenario | Behavior |
|----------|----------|
| Only 1 CVE with a given merge key | No compound created — singleton stays as-is |
| All CVEs share same key | Single compound wrapping all CVEs |
| CVE hidden (type visibility) while merge active | `hideNodeType("CVE")` removes all CVE nodes including compounds; merge state preserved for re-show |
| CVE re-shown after being hidden with merge active | `showNodeType("CVE")` restores nodes; `applyMerge()` re-runs if mode still active |
| Graph rebuilt (settings save) | `resetMerge()` dissolves compounds, resets mode |
| Trivy upload → new data | Graph rebuilt → same as above |
| CVE at depth 0 vs depth 1 with same prereqs | Separate merge groups (depth is part of key) |
| Universal CVE slider (all CVEs merged by ID) | Fewer CVE nodes but still groupable by prereqs/outcomes |
| CVE with no `prereqs` data (shouldn't happen) | Falls into `"unknown:dN"` group — handled gracefully |
| CVE with empty `vc_outcomes` (DoS TI, no VCs) | Groups DoS-only CVEs together — actually useful |
| Bridge edges exist (CPE hidden) | Edges to CVE children route through compound boundary automatically |
| ENABLES edges from VCs to CVEs | Same — Cytoscape routes edges to compound when children are targets |
| Exploit paths filter active | Compound nodes should respect exploit-hidden class — children hidden → compound collapses |
| Environment filter dims CVEs | Dimmed CVEs still participate in merge (visual state preserved inside compound) |
| User selects node inside compound | Click goes to child CVE node; tooltip shows CVE data as normal |
| User drags compound node | Cytoscape moves compound + children together (built-in behavior) |

---

## 9. Test Plan

### 9.1 Python Tests (`tests/test_builder.py`)

**New test class: `TestCVEMergeAttributes`**

```python
class TestCVEMergeAttributes:
    """Tests for CVE node prereqs and vc_outcomes attributes."""

    def test_cve_has_prereqs_attribute(self, loaded_graph_builder):
        """CVE nodes should have a 'prereqs' dict with AV/AC/PR/UI."""
        for nid, data in loaded_graph_builder.graph.nodes(data=True):
            if data.get("node_type") == "CVE":
                assert "prereqs" in data, f"CVE {nid} missing prereqs"
                prereqs = data["prereqs"]
                assert isinstance(prereqs, dict)
                assert set(prereqs.keys()) == {"AV", "AC", "PR", "UI"}

    def test_prereqs_match_cvss_vector(self, loaded_graph_builder):
        """prereqs values should match parsed CVSS vector."""
        for nid, data in loaded_graph_builder.graph.nodes(data=True):
            if data.get("node_type") == "CVE":
                cvss = data.get("cvss_vector", "")
                prereqs = data["prereqs"]
                # Parse CVSS manually to verify
                parts = {}
                for p in cvss.split("/"):
                    if ":" in p:
                        k, v = p.split(":", 1)
                        parts[k] = v
                assert prereqs["AV"] == parts.get("AV", "N")
                assert prereqs["PR"] == parts.get("PR", "N")

    def test_cve_has_vc_outcomes_attribute(self, loaded_graph_builder):
        """CVE nodes should have a 'vc_outcomes' list."""
        for nid, data in loaded_graph_builder.graph.nodes(data=True):
            if data.get("node_type") == "CVE":
                assert "vc_outcomes" in data, f"CVE {nid} missing vc_outcomes"
                assert isinstance(data["vc_outcomes"], list)

    def test_vc_outcomes_match_actual_vc_chain(self, loaded_graph_builder):
        """vc_outcomes should match the actual VC nodes reachable from this CVE."""
        g = loaded_graph_builder.graph
        for nid, data in g.nodes(data=True):
            if data.get("node_type") != "CVE":
                continue
            outcomes = set(tuple(x) for x in data["vc_outcomes"])
            # Trace CVE → CWE → TI → VC manually
            actual = set()
            for cwe in g.successors(nid):
                if g.nodes[cwe].get("node_type") != "CWE":
                    continue
                for ti in g.successors(cwe):
                    if g.nodes[ti].get("node_type") != "TI":
                        continue
                    for vc in g.successors(ti):
                        vc_data = g.nodes[vc]
                        if vc_data.get("node_type") == "VC":
                            actual.add((vc_data["vc_type"], vc_data["value"]))
            assert outcomes == actual, f"CVE {nid}: stored {outcomes} != actual {actual}"

    def test_vc_outcomes_sorted(self, loaded_graph_builder):
        """vc_outcomes should be sorted for stable merge keys."""
        for nid, data in loaded_graph_builder.graph.nodes(data=True):
            if data.get("node_type") == "CVE":
                outcomes = data["vc_outcomes"]
                assert outcomes == sorted(outcomes), f"CVE {nid} outcomes not sorted"

    def test_dos_cve_has_empty_vc_outcomes(self, loaded_graph_builder):
        """CVEs with only DoS TIs (no VC successors) should have empty vc_outcomes."""
        g = loaded_graph_builder.graph
        for nid, data in g.nodes(data=True):
            if data.get("node_type") != "CVE":
                continue
            # Check if all TIs from this CVE are DoS (no VC children)
            has_any_vc = False
            for cwe in g.successors(nid):
                if g.nodes[cwe].get("node_type") != "CWE":
                    continue
                for ti in g.successors(cwe):
                    if g.nodes[ti].get("node_type") != "TI":
                        continue
                    for vc in g.successors(ti):
                        if g.nodes[vc].get("node_type") == "VC":
                            has_any_vc = True
            if not has_any_vc:
                assert data["vc_outcomes"] == [], f"DoS CVE {nid} should have empty outcomes"
```

### 9.2 TypeScript Tests (`frontend/js/features/__tests__/cveMerge.test.ts`)

```typescript
// Test cases:

describe('cveMerge', () => {
    describe('isMergeAvailable', () => {
        it('returns false when nothing is hidden');
        it('returns false when only CWE is hidden');
        it('returns false when only TI is hidden');
        it('returns true when both CWE and TI are hidden');
        it('returns true when CWE, TI, and VC are all hidden');
    });

    describe('computePrereqKey', () => {
        it('creates key from prereqs dict on node data');
        it('includes chain_depth in key');
        it('returns "unknown" for nodes without prereqs');
        it('groups nodes with identical prereqs under same key');
        it('separates nodes at different depths');
    });

    describe('computeOutcomeKey', () => {
        it('creates key from vc_outcomes array on node data');
        it('includes chain_depth in key');
        it('returns "unknown" for nodes without vc_outcomes');
        it('handles empty vc_outcomes (DoS CVEs)');
        it('produces same key for same outcome set regardless of order');
    });

    describe('formatMergeLabel', () => {
        it('formats prereq key as "AV:N / AC:L / PR:N / UI:N (×3)"');
        it('formats outcome key as "→ AV:L, EX:Y, PR:H (×2)"');
        it('strips depth suffix from display');
    });

    describe('applyMerge', () => {
        it('creates compound parent nodes for groups with 2+ CVEs');
        it('does not create compounds for singleton groups');
        it('moves child CVEs into compound parent');
        it('cleans up previous merge before applying new one');
    });

    describe('removeMerge', () => {
        it('moves children back to root level');
        it('removes compound parent nodes');
        it('clears mergeParentIds array');
        it('is safe to call when no merge is active');
    });

    describe('setMergeMode', () => {
        it('calls applyMerge for prereqs mode');
        it('calls applyMerge for outcomes mode');
        it('calls removeMerge for none mode');
        it('updates button active class');
    });

    describe('toast', () => {
        it('shows toast when merge becomes available for the first time');
        it('does not show toast on subsequent hide/show cycles');
        it('toast auto-dismisses after 4 seconds');
    });

    describe('auto-disable', () => {
        it('resets merge when CWE is re-shown');
        it('resets merge when TI is re-shown');
        it('hides merge button when conditions unmet');
    });
});
```

### 9.3 E2E Tests (`tests/test_frontend.py`) — optional stretch

```python
class TestCVEMerge:
    """E2E tests for CVE merge functionality."""

    def test_merge_button_hidden_by_default(self, page):
        """⊞ button should not be visible initially."""

    def test_merge_button_appears_when_cwe_ti_hidden(self, page):
        """⊞ button appears after hiding both CWE and TI."""

    def test_merge_by_prereqs_creates_compound_nodes(self, page):
        """Selecting 'By Prerequisites' groups CVEs into compound nodes."""

    def test_merge_by_outcomes_creates_compound_nodes(self, page):
        """Selecting 'By Outcomes' groups CVEs into compound nodes."""

    def test_merge_auto_disables_on_cwe_show(self, page):
        """Showing CWE dissolves merge and hides button."""

    def test_merge_resets_on_graph_rebuild(self, page):
        """Changing settings and rebuilding graph resets merge."""
```

---

## 10. File Change Summary

| File | Type | Change Description |
|------|------|--------------------|
| `src/graph/builder.py` | Edit | Add `prereqs` dict and `vc_outcomes` list to CVE nodes in `_build_cve_chain()` (~10 lines) |
| `frontend/js/features/cveMerge.ts` | **New** | Merge state management, compound node creation/removal, button handlers (~180 lines) |
| `frontend/index.html` | Edit | Add `⊞` button to CVE row + merge popover div (~10 lines) |
| `frontend/css/styles.css` | Edit | Merge button, popover, compound node styles (~50 lines) |
| `frontend/js/config/constants.ts` | Edit | Add `CVE_GROUP` compound node Cytoscape style (~15 lines) |
| `frontend/js/features/filter.ts` | Edit | Import cveMerge; call `updateMergeButtonVisibility()` in hide/show/reset (~8 lines) |
| `frontend/js/ui/modal.ts` | Edit | Import cveMerge; call `resetMerge()` in `saveSettings()` (~3 lines) |
| `frontend/js/main.ts` | Edit | Import and call `setupMergeButton()` in `init()` (~3 lines) |
| `tests/test_builder.py` | Edit | New `TestCVEMergeAttributes` class (~60 lines) |
| `frontend/js/features/__tests__/cveMerge.test.ts` | **New** | Unit tests for merge logic (~150 lines) |

**Total estimated**: ~490 lines across 10 files (2 new).

---

## 11. Implementation Order

| Step | Description | Dependencies | Testable? |
|------|-------------|--------------|-----------|
| 1 | Backend: add `prereqs` + `vc_outcomes` to CVE nodes | None | Yes — Python tests |
| 2 | Python tests for new CVE attributes | Step 1 | Run tests |
| 3 | Frontend: `CVE_GROUP` Cytoscape style | None | Visual |
| 4 | Frontend: `cveMerge.ts` — state + compound logic | Step 3 | TS unit tests |
| 5 | Frontend: HTML (button + popover) | None | Visual |
| 6 | Frontend: CSS (button + popover styles) | Step 5 | Visual |
| 7 | Frontend: wire `filter.ts` → merge visibility | Steps 4, 5 | Manual test |
| 8 | Frontend: wire `modal.ts` → merge reset | Step 4 | Manual test |
| 9 | Frontend: wire `main.ts` → init | Steps 4, 5 | Manual test |
| 10 | TypeScript unit tests | Step 4 | Run tests |
| 11 | E2E tests (stretch) | All above | Run tests |
| 12 | Light theme CSS variants | Step 6 | Visual |

Steps 1-2 (backend) and steps 3, 5-6 (frontend static) can run **in parallel**.
