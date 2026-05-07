# Paper-ready algorithms: granularity slider, type-toggle bridges, CVE merge

This document is a self-contained reference of the three reduction mechanisms PAGDrawer ships, written in the style of a GD paper algorithm appendix. Each mechanism is described in three layers:

1. **Intent** — what the mechanism does for the user, and why it preserves attack-graph soundness.
2. **Pseudocode** — paper-ready, language-agnostic, suitable for direct inclusion in the paper body or appendix.
3. **TypeScript** — the production source verbatim (with line refs into the codebase) so a reviewer can verify pseudocode against the implementation.

> **Source pinning.** Line numbers are accurate as of commit [`130f20b`](https://github.com/tmachalewski/PAGDrawer/commit/130f20b) on `main` (2026-05-05). Function names are stable identifiers — even if line numbers drift, `grep -n 'export function NAME'` resolves them.

---

## 1. Granularity slider

### 1.1 Intent

Each non-anchor node type $T \in \{\text{CPE}, \text{CVE}, \text{CWE}, \text{TI}, \text{VC}\}$ has a slider whose positions correspond to the chain of ancestor types in the schema:

$$\text{ATTACKER} \to \text{HOST} \to \text{CPE} \to \text{CVE} \to \text{CWE} \to \text{TI} \to \text{VC}$$

A slider position $g(T)$ chooses the *grouping level* for $T$: every node of type $T$ that shares the same chain of ancestors **up to** $g(T)$ collapses into a single representative. Pulling the slider toward `ATTACKER` is more aggressive grouping (fewer survivors); pulling it toward the schema's own type is most-granular (each instance keeps its own context).

The slider is **monotone**: $g(T)$ can only be an ancestor of $T$ — never a descendant — which guarantees that the grouped node-id is uniquely determined by the chosen ancestor chain. This monotonicity is what lets the metric layer treat granularity as a clean structural reduction (no soundness side-effects).

A second axis of the same control is the **`skip_layer_2`** boolean, which suppresses construction of the internal-network sublayer entirely. When set, the `INSIDE_NETWORK` bridge node is still emitted with `ENTERS_NETWORK` edges from L1 `EX:Y` nodes, but no L2 hosts / CPEs / CVEs are materialised — useful when the analyst only wants the external-surface story.

### 1.2 Pseudocode

```
INPUT:  node type T, slider position p ∈ {0, 1, …, |chain(T)|-1}
OUTPUT: grouping level g(T), used downstream during graph construction
        to determine the node identity hash for every instance of T.

const chain : Map<NodeType, NodeType[]> = {
    HOST → [ATTACKER],
    CPE  → [ATTACKER, HOST],
    CVE  → [ATTACKER, HOST, CPE],
    CWE  → [ATTACKER, HOST, CPE, CVE],
    TI   → [ATTACKER, HOST, CPE, CVE, CWE],
    VC   → [ATTACKER, HOST, CPE, CVE, CWE, TI]
}

function slider_to_level(T, p):
    options := chain[T]
    if p < 0 or p ≥ |options|:
        return ATTACKER                     ;; defensive default
    return options[p]

function node_id_with_grouping(node, g):
    ;; g = slider-driven grouping level.
    ;; Build the identity hash from the *prefix* of the schema up to g.
    levels := schema_prefix_until(g)        ;; e.g. g=CPE  → [ATTACKER, HOST, CPE]
    fields := []
    for L in levels:
        fields.append(node.context_field(L))
    fields.append(node.intrinsic_id())      ;; e.g. CVE-2024-12345
    return hash(fields)
```

Two instances of $T$ with identical `fields` collapse to one node; otherwise they are distinct. Because the schema is a chain, `fields` is a prefix of node identity — there is no merge ambiguity.

### 1.3 Source

Three files participate. The frontend slider UI converts UI position ↔ canonical level name; the backend stores the grouping config and uses it during graph construction.

**Frontend slider mapping** — `frontend/js/ui/modal.ts:17–95`:

```typescript
// Node types and their grouping options (chain from ATTACKER to parent)
const SLIDER_OPTIONS: Record<string, string[]> = {
    CPE: ['ATTACKER', 'HOST'],
    CVE: ['ATTACKER', 'HOST', 'CPE'],
    CWE: ['ATTACKER', 'HOST', 'CPE', 'CVE'],
    TI:  ['ATTACKER', 'HOST', 'CPE', 'CVE', 'CWE'],
    VC:  ['ATTACKER', 'HOST', 'CPE', 'CVE', 'CWE', 'TI'],
};

function configToSliderPosition(type: string, configValue: string): number {
    const options = SLIDER_OPTIONS[type];
    if (!options) return 0;

    // Handle legacy 'universal' value
    if (configValue === 'universal' || configValue === 'ATTACKER') return 0;

    const index = options.indexOf(configValue);
    if (index >= 0) return index;

    // Handle legacy 'singular' — map to most granular
    if (configValue === 'singular') return options.length - 1;

    return options.length - 1;
}

function sliderPositionToConfig(type: string, position: number): string {
    const options = SLIDER_OPTIONS[type];
    if (!options || position < 0 || position >= options.length) return 'ATTACKER';
    return options[position];
}
```

**Backend grouping config** — `src/core/config.py:14–96`:

```python
# Hierarchy of grouping levels (from least to most granular)
GROUPING_HIERARCHY = ["ATTACKER", "HOST", "CPE", "CVE", "CWE", "TI", "VC"]

# Valid grouping levels for each node type (can only group by ancestors)
VALID_GROUPINGS: Dict[str, list] = {
    "HOST": ["ATTACKER"],                            # HOST is always per-attacker
    "CPE":  ["ATTACKER", "HOST"],
    "CVE":  ["ATTACKER", "HOST", "CPE"],
    "CWE":  ["ATTACKER", "HOST", "CPE", "CVE"],
    "TI":   ["ATTACKER", "HOST", "CPE", "CVE", "CWE"],
    "VC":   ["ATTACKER", "HOST", "CPE", "CVE", "CWE", "TI"],
}

@dataclass
class GraphConfig:
    """Configuration for how the graph is built."""

    node_modes: Dict[str, DuplicationMode] = field(default_factory=lambda: {
        "HOST": "ATTACKER",   # Hosts are always unique anchors (universal)
        "CPE":  "HOST",
        "CVE":  "CPE",
        "CWE":  "CVE",
        "TI":   "CWE",
        "VC":   "TI",
    })
    skip_layer_2: bool = False

    def _normalize_mode(self, node_type: str, mode: str) -> str:
        if mode == "universal":
            return "ATTACKER"
        if mode == "singular":
            valid = VALID_GROUPINGS.get(node_type, ["ATTACKER"])
            return valid[-1] if valid else "ATTACKER"
        return mode

    def get_grouping_level(self, node_type: str) -> str:
        return self._normalize_mode(node_type, self.node_modes.get(node_type, "ATTACKER"))
```

**Node-id construction** uses `should_include_context(node_type, context_type)` to decide whether each ancestor's id should be folded into the hash, given the chosen grouping level.

---

## 2. Type toggle (visibility, with bridge edges)

### 2.1 Intent

When the user clicks the eye icon next to a type $T$ in the sidebar, every visible node of that type is removed and replaced by **bridge edges** between its visible predecessors and successors. The bridge replaces the hidden node's contribution to reachability: if there was a directed path $p \to n \to s$ with $\text{type}(n) = T$, a synthetic edge $p \to s$ takes its place.

Bridges compose: hiding two layers in sequence yields second-generation bridges whose `chain_length` is the *sum* of the two hops — exactly the M19 contraction-depth metric. The chain accumulates through the recurrence

$$\text{chain}(p \to s) \;=\; \text{chain}(p \to n) \;+\; 1 \;+\; \text{chain}(n \to s),$$

where the chain of an *original* (non-bridge) edge is 0 by convention. Because the recurrence is additive in the prior chain, a bridge created over an already-bridged predecessor or successor inherits the accumulated length.

**Show-after-hide is implemented via full restore-then-rehide.** Naive incremental restoration would leave previously-restored nodes as dead ends (their edges to still-hidden types can't be restored). Instead, when the user un-hides a type, all hidden nodes/edges are restored, all bridges are removed, and the remaining hidden-types are re-applied via `hideNodeType` in turn. This guarantees the visible graph is always identical to a single-pass hide of the current `hiddenTypes` set.

### 2.2 Pseudocode

```
function hide_node_type(T, V, E, hidden):
    ;; V = current visible nodes, E = current visible edges
    ;; hidden = set of type names hidden so far (T about to join)
    nodes_to_hide := { n ∈ V : type(n) = T }
    bridges := []

    for n in nodes_to_hide:
        incomers := { p ∈ V : (p, n) ∈ E ∧ type(p) ∉ hidden }
        outgoers := { s ∈ V : (n, s) ∈ E ∧ type(s) ∉ hidden }

        for p in incomers:
            for s in outgoers:
                id := "typebridge_" + T + "_" + p.id + "_" + s.id
                if id ∉ E:
                    in_chain  := chain_of(edge p → n)            ;; 0 for original
                    out_chain := chain_of(edge n → s)            ;; 0 for original
                    chain     := in_chain + 1 + out_chain        ;; M19 recurrence

                    types     := distinct edge-types incident on n     ;; for colour
                    colour    := bright_average(types)

                    add bridge edge p → s with
                        type = "BRIDGE",
                        bridge_for_type = T,
                        hidden_edge_types = types,
                        bridge_colour = colour,
                        chain_length = chain

    remove every n ∈ nodes_to_hide and its non-bridge edges
    return bridges

function show_node_type(T, hidden):
    to_remain_hidden := hidden \ {T}

    remove every existing bridge from the graph
    restore every hidden node from storage
    restore every hidden non-bridge edge from storage
    clear all hidden-state storage

    for T' in to_remain_hidden:
        hide_node_type(T', V_now, E_now, hidden_so_far ∪ {T'})

    if T ∈ {CWE, TI}: disable CVE merge          ;; merge requires CWE+TI hidden
```

### 2.3 Source — `frontend/js/features/filter.ts:32–294`

The chain-length helper:

```typescript
function readChainLength(edges: { length: number; data: (k: string) => unknown }): number {
    if (edges.length === 0) return 0;
    const v = edges.data('chain_length');
    return typeof v === 'number' && Number.isFinite(v) ? v : 0;
}
```

The hide path (M19's chain_length recurrence is the highlighted block):

```typescript
function hideNodeType(type: string): void {
    const cy = getCy();
    if (!cy) return;

    hiddenTypes.add(type);
    const nodesToHide = cy.nodes(`[type="${type}"]`);

    nodesToHide.forEach(node => {
        const incomers = node.incomers('node').filter(n => !hiddenTypes.has(n.data('type')));
        const outgoers = node.outgoers('node').filter(n => !hiddenTypes.has(n.data('type')));

        incomers.forEach(pred => {
            outgoers.forEach(succ => {
                const bridgeId = `typebridge_${type}_${pred.id()}_${succ.id()}`;
                if (cy.getElementById(bridgeId).length === 0) {
                    const hiddenEdgeTypes: string[] = [];
                    node.connectedEdges().forEach(edge => {
                        if (!edge.data('isBridge')) {
                            const t = edge.data('type');
                            if (t && !hiddenEdgeTypes.includes(t)) hiddenEdgeTypes.push(t);
                        }
                    });
                    const bridgeColor = computeBridgeColor(hiddenEdgeTypes);

                    // M19 recurrence: chain = incoming + 1 + outgoing
                    const incomingChain = readChainLength(pred.edgesTo(node));
                    const outgoingChain = readChainLength(node.edgesTo(succ));
                    const chainLength   = incomingChain + 1 + outgoingChain;

                    cy.add({
                        group: 'edges',
                        data: {
                            id: bridgeId,
                            source: pred.id(),
                            target: succ.id(),
                            type: 'BRIDGE',
                            isBridge: true,
                            bridgeForType: type,
                            hiddenEdgeTypes,
                            bridgeColor,
                            chain_length: chainLength,
                        },
                    });
                }
            });
        });
        // … node and original-edge data are stored for later restoration
    });

    nodesToHide.remove();
    updateMergeButtonVisibility();
}
```

The show path (full restore-then-rehide):

```typescript
function showNodeType(type: string): void {
    const cy = getCy();
    if (!cy) return;

    const typesToRemainHidden = new Set(hiddenTypes);
    typesToRemainHidden.delete(type);

    cy.edges('[isBridge]').remove();                        // all bridges gone
    hiddenByType.forEach(d => d.nodes.forEach(n => {        // restore nodes
        if (cy.getElementById(n.data?.id as string).length === 0) cy.add(n);
    }));
    hiddenTypes.clear();
    globalHiddenEdges.forEach((edgeData, edgeId) => {       // restore edges
        if (cy.getElementById(edgeId).length === 0) cy.add(edgeData);
    });
    hiddenByType.clear();
    typeBridgeEdges.clear();
    globalHiddenEdges.clear();

    typesToRemainHidden.forEach(t => hideNodeType(t));      // re-apply remaining hides

    if (type === 'CWE' || type === 'TI') removeMerge();     // CVE-merge requires CWE+TI hidden
    updateMergeButtonVisibility();
}
```

**Why full restore-then-rehide?** A naive incremental "show $T$ only" would leave restored nodes whose edges to still-hidden types can't be brought back, producing dead ends. The restore-and-rehide pattern guarantees the visible graph after every toggle is identical to what a single-pass `hideNodeType` over the current `hiddenTypes` would produce — composition order doesn't matter.

---

## 3. CVE merge (compound nodes by prerequisites or outcomes)

### 3.1 Intent

CVE merge groups CVE nodes into Cytoscape **compound parents** based on a structural key. It activates only when the user has hidden both `CWE` and `TI` (the two layers between CVE and VC); otherwise the per-CVE outcome edges still connect to distinct downstream nodes and grouping is meaningless.

Two modes:

- **`prereqs`** — CVEs sharing the same CVSS prerequisite vector (`AV / AC / PR / UI`) collapse. Surfaces "all the CVEs an attacker with profile $X$ can exploit."
- **`outcomes`** — CVEs sharing the same set of vulnerability-condition outcomes (`vc_outcomes`, ordered by the backend) collapse. Surfaces "all the CVEs that grant the same downstream effects."

In `outcomes` mode, edges are also **consolidated**: every original edge from a merged CVE to a non-group node is hidden (`display: none`), and a single deduplicated synthetic edge is created from the compound parent. Originals retain identity for hover; the consolidated graph reads as a structural summary. In `prereqs` mode no edge consolidation happens — the prereq-key is informative for the analyst but the outgoing edges already differ per-CVE.

The merge key always includes the CVE's **layer (L1/L2)** and **`chain_depth`** as suffix. Two CVEs with identical prerequisites but different attack-graph depth must not collapse — that would conflate "vulnerability at the perimeter" with "vulnerability after the first hop."

### 3.2 Pseudocode

```
function compute_prereq_key(cve):
    if cve.prereqs is null:    return "unknown|" + cve.layer + "|d" + cve.chain_depth
    return "AV:" + p.AV + "|AC:" + p.AC + "|PR:" + p.PR + "|UI:" + p.UI
         + "|" + cve.layer + "|d" + cve.chain_depth

function compute_outcome_key(cve):
    if cve.vc_outcomes is null or empty:   return "none|" + cve.layer + "|d" + cve.chain_depth
    parts := [ t + ":" + v  for (t, v) in cve.vc_outcomes ]
    return join(parts, ",") + "|" + cve.layer + "|d" + cve.chain_depth

function apply_merge(mode):
    ;; mode ∈ {prereqs, outcomes}
    cves := visible CVE nodes that are NOT exploit-hidden
    groups := empty map<string, [node_id]>

    for each c in cves:
        key := mode = prereqs ? compute_prereq_key(c) : compute_outcome_key(c)
        groups[key].append(c.id)

    for each (key, ids) in groups:
        if |ids| < 2: continue              ;; size-1 groups are not merged

        parent_id := "cve_merge_" + mode + "_" + key
        add compound parent node:
            type    = "CVE_GROUP",
            label   = format_label(key, |ids|, mode),
            mergeKey, mergeMode

        reparent every id in ids into parent_id

        if mode = outcomes:
            seen_keys := empty set
            for each id in ids:
                for each edge incident on node id:
                    other := the endpoint that is NOT this CVE
                    if other ∈ ids: skip                         ;; intra-group edge
                    edge_key := (direction, other, edge.type)
                    edge.display := none                          ;; hide original
                    if edge_key ∈ seen_keys: continue             ;; dedupe
                    seen_keys.add(edge_key)
                    add synthetic edge between parent and other,
                        with same type and synthetic = true
```

`format_label` strips the layer/depth suffix for readability and counts the group size. Layer/depth stay in the *key* (and thus in the parent-id) so that distinct layers/depths cannot collide.

### 3.3 Source

**Pure key functions** — `frontend/js/features/mergeKeys.ts:43–60`:

```typescript
export interface CveKeyData {
    prereqs?:     { AV?: string; AC?: string; PR?: string; UI?: string } | null;
    vc_outcomes?: ReadonlyArray<readonly [string, string]> | null;
    chain_depth?: number;
    layer?:       string;
}

/** Pure prereq-key computation — testable without Cytoscape. */
export function computePrereqKeyFromData(d: CveKeyData): string {
    const depth = d.chain_depth ?? 0;
    const layer = d.layer ?? 'L1';
    if (!d.prereqs) return `unknown|${layer}|d${depth}`;
    return `AV:${d.prereqs.AV}|AC:${d.prereqs.AC}|PR:${d.prereqs.PR}|UI:${d.prereqs.UI}|${layer}|d${depth}`;
}

/** Pure outcome-key computation — testable without Cytoscape. */
export function computeOutcomeKeyFromData(d: CveKeyData): string {
    const depth = d.chain_depth ?? 0;
    const layer = d.layer ?? 'L1';
    if (!d.vc_outcomes || !Array.isArray(d.vc_outcomes)) {
        return `unknown|${layer}|d${depth}`;
    }
    // outcomes is [["AV","L"], ["EX","Y"], ["PR","H"]] — already sorted by backend
    const key = d.vc_outcomes.map(([t, v]) => `${t}:${v}`).join(',');
    return `${key || 'none'}|${layer}|d${depth}`;
}
```

**Merge application** — `frontend/js/features/cveMerge.ts:116–204`:

```typescript
export function applyMerge(): void {
    removeMerge();
    const cy = getCy();
    if (!cy || currentMergeMode === 'none') return;

    // Skip exploit-hidden CVEs: merging invisible children would strand
    // the compound parent at (0,0) under dagre layout.
    const cveNodes = cy.nodes('[type="CVE"]')
                       .filter(n => !n.hasClass('exploit-hidden'));
    const groups: Map<string, string[]> = new Map();

    cveNodes.forEach(node => {
        const key = currentMergeMode === 'prereqs'
            ? computePrereqKey(node)
            : computeOutcomeKey(node);
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key)!.push(node.id());
    });

    groups.forEach((nodeIds, key) => {
        if (nodeIds.length < 2) return;          // size-1 groups stay un-merged

        const parentId = `cve_merge_${currentMergeMode}_${key}`;
        cy.add({
            group: 'nodes',
            data: {
                id: parentId,
                type: 'CVE_GROUP',
                label: formatMergeLabel(key, nodeIds.length, currentMergeMode),
                mergeKey: key,
                mergeMode: currentMergeMode,
            },
        });

        const nodeIdSet = new Set(nodeIds);
        nodeIds.forEach(id => cy.getElementById(id).move({ parent: parentId }));

        // Edge consolidation only in outcomes mode
        if (currentMergeMode === 'outcomes') {
            const seenEdges = new Set<string>();
            nodeIds.forEach(id => {
                const node = cy.getElementById(id);
                node.connectedEdges().forEach(edge => {
                    const srcId   = edge.source().id();
                    const tgtId   = edge.target().id();
                    const isSource = srcId === id;
                    const otherId  = isSource ? tgtId : srcId;
                    if (nodeIdSet.has(otherId)) return;       // intra-group edge

                    const edgeType = edge.data('type') || '';
                    const edgeKey  = `${isSource ? 'out' : 'in'}|${otherId}|${edgeType}`;

                    edge.style('display', 'none');           // hide original
                    if (seenEdges.has(edgeKey)) return;      // dedupe
                    seenEdges.add(edgeKey);

                    const synId = `syn_${parentId}_${edgeKey}`;
                    cy.add({
                        group: 'edges',
                        data: {
                            id: synId,
                            source: isSource ? parentId : otherId,
                            target: isSource ? otherId  : parentId,
                            type:   edgeType,
                            synthetic: true,
                        },
                    });
                });
            });
        }
    });

    runLayout();
}
```

**Label formatting** — `frontend/js/features/mergeKeys.ts:92–102`:

```typescript
export function formatMergeLabel(key: string, count: number, mode: MergeMode): string {
    // Strip layer and depth suffixes for display: "AV:N|...|L1|d0" → "AV:N|..."
    const cleanKey = key.replace(/\|L\d+\|d\d+$/, '');

    if (mode === 'prereqs') {
        return cleanKey.replace(/\|/g, ' / ') + ` (×${count})`;
    } else {
        if (cleanKey === 'none') return `→ no VCs (×${count})`;
        return '→ ' + cleanKey.replace(/,/g, ', ') + ` (×${count})`;
    }
}
```

---

## 4. Composition guarantees

The three mechanisms compose under a recommended ordering — **granularity → visibility → merge → exploit paths** — that the metric layer is built around:

| Pair | Why this order |
|---|---|
| Granularity before visibility | Granularity is a structural reduction at construction time; visibility is a runtime overlay. Reversing makes no operational sense — visibility operates on whatever the slider produced. |
| Visibility before merge | Merge requires `CWE` and `TI` hidden (it is gated in the UI). The merge key includes `chain_depth`; running merge on a graph where bridges haven't yet collapsed the inner layers would group CVEs that the visibility step would later reveal as structurally distinct. |
| Merge before exploit-paths is **not** required | Exploit paths is a task-driven pruning that hides off-path nodes without changing identity. It commutes with merge: applying it before merge just means fewer CVEs go into the grouping pass; applying it after means some compound parents may end up with all children in `exploit-hidden`. The current implementation skips exploit-hidden CVEs at merge time (line 125 of `cveMerge.ts`) so the second order doesn't strand parents. |

**Why these orderings keep the metrics honest.** M19's `chain_length` recurrence assumes bridges are created sequentially (visibility-first); merge does not touch `chain_length`, which is asserted as a regression sentinel (`metrics.test.ts` → "cveMerge does not touch chain_length"). M20's ECR is computed only over compounds with at least one synthetic edge, so it skips `ATTACKER_BOX` and `prereqs`-mode parents cleanly. M22's ACR uses the same merge keys (extracted into `mergeKeys.ts` as a pure two-tier API) so the metric and the merge mechanism share a single source of truth — the metric "predicts" the actual reduction the user would see.

A summary of the soundness invariants the three mechanisms preserve:

| Mechanism | Reachability | Node identity | Edge type-pairs |
|---|---|---|---|
| Granularity | Preserved up to grouping | Hashed by ancestor chain | Preserved per group |
| Type toggle | Preserved via bridges | Survivors keep id; bridges are synthetic but typed `BRIDGE` | Hidden types fold into bridge `hiddenEdgeTypes` array |
| CVE merge | Preserved (children remain in graph; outcomes-mode synthetic edges deduplicated, originals `display:none`) | Children keep id; compound parent has stable id `cve_merge_<mode>_<key>` | Synthetic edges retain original `type`; carry `synthetic: true` flag |

---

## 5. Cross-references

- M19 (chain_length) full discussion: `MetricsPaperReference.md § 2`, § 5.7. Sentinel tests: `metrics.test.ts → chain_length invariants (caveat 4.11.2 sentinel)`.
- M20 (ECR) for outcomes-merge consolidation strength: `MetricsPaperReference.md § 5.8`.
- M22 (ACR) for granularity-as-compression theory: `MetricsPaperReference.md § 2`, `mergeKeys.ts`.
- Five-step pipeline + worked nginx numbers: `MetricsPaperReference.md § 6`.
- Granularity slider UI walkthrough: `ReadabilityUniversalitySingularitySliders.md`.
- CVE merge UI walkthrough and decision criteria: `CVEMergeModes.md`.
