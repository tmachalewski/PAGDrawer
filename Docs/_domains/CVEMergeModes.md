# CVE Merge Modes

This document describes how PAGDrawer visually merges CVE nodes using Cytoscape compound (parent) nodes when intermediate graph layers (CWE, TI) are hidden.

---

## Motivation

When CWE and TI nodes are hidden via visibility toggles, the graph shows only CPE → CVE → VC paths. Many CVEs share identical CVSS prerequisites or produce identical VC outcomes. Merging these into compound boxes:

- Reduces visual clutter (10 individual CVE nodes → 2 grouped boxes)
- Reveals structural patterns ("these 5 CVEs all require network access with no auth")
- Preserves individual CVE inspection via hover tooltips inside the compound

---

## Availability

Merge is available only when **both CWE and TI** node types are hidden. This condition exists because:

1. With CWE/TI visible, CVEs are already connected to their outcomes via the full chain
2. Merging with intermediate nodes visible would create confusing compound/edge overlap

The merge button (`⊞`) is always visible in the CVE sidebar row but **disabled** (greyed out) until CWE+TI are both hidden. The disabled tooltip reads: "Hide CWE and TI nodes to enable merging".

---

## Merge Strategies

### By Prerequisites (AV/AC/PR/UI)

Groups CVEs that require the same CVSS attack conditions to exploit.

**Key computation**: Extracts `AV`, `AC`, `PR`, `UI` from the CVE's `prereqs` attribute (parsed from CVSS vector on the backend).

**Example key**: `AV:N|AC:L|PR:N|UI:N|L1|d0`

**Label format**: `AV:N / AC:L / PR:N / UI:N (×5)`

**Use case**: "Show me which groups of CVEs an attacker at each privilege level can exploit."

**Edge behavior**: Individual edges preserved — CVEs in a prereqs group may connect to different CPEs/VCs, so consolidation would lose information.

### By Outcomes (same VCs)

Groups CVEs that produce the same set of Vector Changer states when exploited.

**Key computation**: Uses the CVE's `vc_outcomes` attribute — a sorted list of `[vc_type, vc_value]` pairs representing all VCs produced through the CVE → CWE → TI → VC chain.

**Example key**: `AV:L,EX:Y,PR:H|L1|d0`

**Label format**: `→ AV:L, EX:Y, PR:H (×3)`

**Special case**: CVEs with no VC outcomes (DoS-only) get key `none|L1|d0` and label `→ no VCs (×2)`.

**Use case**: "Show me which CVEs are interchangeable from an attacker's perspective."

**Edge behavior**: Edges consolidated — since all CVEs in the group connect to the same VCs, individual edges are hidden and replaced with deduped synthetic edges from the compound parent. This typically halves the visible edge count.

---

## Merge Key Structure

Every merge key includes three discriminators to prevent incorrect grouping:

```
<prereqs-or-outcomes> | <layer> | d<chain_depth>
```

| Component | Values | Purpose |
|-----------|--------|---------|
| Prereqs/Outcomes | CVSS values or VC pairs | Core grouping criterion |
| Layer | `L1`, `L2` | Prevents merging across attack layers |
| Chain Depth | `d0`, `d1`, `d2`, ... | Prevents merging across attack stages |

### Why Layer Matters

The same CVE (e.g., CVE-2024-4741) can appear on both L1 (external attack surface) and L2 (internal network) with identical prereqs and chain_depth=0. Without layer discrimination, a single compound would span both visual layers, creating a huge box.

### Why Depth Matters

A CVE exploitable at depth 0 (directly) and depth 1 (after privilege escalation) represents different attack stages. Merging them would conflate "initial compromise" with "post-compromise exploitation".

---

## Implementation: Compound Nodes

CVE_GROUP nodes are Cytoscape **compound parent nodes** — they act as visual containers for their children.

### How It Works

1. **Group CVEs**: Compute merge key for each visible CVE node, group by key
2. **Create compound**: For groups with 2+ members, add a `CVE_GROUP` parent node
3. **Reparent children**: Move CVE nodes into the compound via `node.move({ parent: groupId })`
4. **Consolidate edges** (outcomes only): Hide individual edges, create deduped synthetic edges from parent
5. **Re-layout**: Run dagre layout to position compounds compactly

### Dissolving Merge

1. **Restore edges**: Show hidden edges, remove synthetic edges
2. **Unparent children**: Move CVE nodes back to root via `node.move({ parent: null })`
3. **Remove compound**: Delete the CVE_GROUP node
4. **Re-layout**: Redistribute nodes

### CVE_GROUP Node Style

```
Background: rgba(234, 179, 8, 0.12)  (semi-transparent yellow)
Border: 2px dashed #eab308           (yellow dashed)
Label: top-center, 10px              (e.g., "AV:N / AC:L / PR:N / UI:N (×5)")
Padding: 12px
Shape: round-rectangle
```

---

## Edge Consolidation (Outcomes Mode)

In outcomes mode, edge consolidation eliminates redundant edges:

### Before Consolidation
```
CVE-1 ──→ VC:AV:L
CVE-2 ──→ VC:AV:L
CVE-3 ──→ VC:AV:L
CPE-A ──→ CVE-1
CPE-B ──→ CVE-2
CPE-A ──→ CVE-3
```
(6 edges)

### After Consolidation
```
[CVE_GROUP] ──→ VC:AV:L     (1 deduped outgoing)
CPE-A ──→ [CVE_GROUP]       (1 deduped incoming)
CPE-B ──→ [CVE_GROUP]       (1 deduped incoming)
```
(3 edges — individual CVEs still visible inside the compound box)

### Deduplication Logic

Edges are deduped by `(direction, otherNodeId, edgeType)`. If multiple CVEs in the same group connect to the same external node with the same edge type, only one synthetic edge is created.

---

## Data Flow

### Backend (builder.py)

```python
# prereqs — parsed from CVSS vector
prereqs = {
    "AV": cvss_parts.get("AV", "N"),
    "AC": cvss_parts.get("AC", "L"),
    "PR": cvss_parts.get("PR", "N"),
    "UI": cvss_parts.get("UI", "N"),
}
graph.add_node(cve_id, ..., prereqs=prereqs)

# vc_outcomes — collected after CWE→TI→VC chain is built
vc_outcomes = sorted(set((vc_type, vc_value) for vc_type, vc_value, _ in all_vc_info))
graph.nodes[cve_id]["vc_outcomes"] = [list(pair) for pair in vc_outcomes]
```

### Frontend (cveMerge.ts)

```typescript
// Key computation includes layer + depth
function computePrereqKey(node): string {
    const prereqs = node.data('prereqs');
    const depth = node.data('chain_depth') ?? 0;
    const layer = node.data('layer') ?? 'L1';
    return `AV:${prereqs.AV}|AC:${prereqs.AC}|PR:${prereqs.PR}|UI:${prereqs.UI}|${layer}|d${depth}`;
}
```

---

## Circular Dependency Resolution

`cveMerge.ts` needs `getHiddenTypes()` from `filter.ts` to check merge availability. But `filter.ts` imports `updateMergeButtonVisibility()` from `cveMerge.ts` to update the button when visibility changes. This creates a circular import.

**Solution**: Dependency injection via `injectGetHiddenTypes(fn)`:

```typescript
// cveMerge.ts — declares injectable dependency
let _getHiddenTypes: () => Set<string> = () => new Set();
export function injectGetHiddenTypes(fn: () => Set<string>): void {
    _getHiddenTypes = fn;
}

// main.ts — injects during init
import { injectGetHiddenTypes } from './features/cveMerge';
import { getHiddenTypes } from './features/filter';
injectGetHiddenTypes(getHiddenTypes);
```

---

## UI Components

### Merge Button (`⊞`)

- Located in CVE sidebar row, left of visibility toggle
- Always visible; disabled (greyed out, `opacity: 0.35`) when CWE+TI not hidden
- Disabled tooltip: "Hide CWE and TI nodes to enable merging"
- Enabled tooltip: "Merge CVE nodes"
- Active state: glowing border when a merge mode is active

### Popover Menu

Three options appearing below the button on click:
- **No Merge** — removes any active merge
- **By Prerequisites (AV/AC/UI/PR)** — groups by CVSS prereqs
- **By Outcomes (same VCs)** — groups by VC outcomes

### Toast Notification

One-time notification shown when merge first becomes available:
- "CVE merging now available — click ⊞ on CVE row"
- Auto-dismisses after 4 seconds or on click
- Only shown once per session

---

## Integration Points

| Module | Integration |
|--------|-------------|
| `filter.ts` | Calls `updateMergeButtonVisibility()` after hide/show type; calls `removeMerge()` on show to auto-disable |
| `modal.ts` | Calls `resetMerge()` on settings save (graph rebuild) |
| `main.ts` | Injects dependency, calls `setupMergeButton()` during init |
| `constants.ts` | Defines `CVE_GROUP` node style |
| `layout.ts` | `runLayout()` called after merge/unmerge for compact positioning |
