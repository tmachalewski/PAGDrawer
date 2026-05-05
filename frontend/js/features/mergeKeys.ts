/**
 * Pure merge-key functions used by:
 *   - cveMerge.ts (the merge mechanism — outcomes/prereqs grouping)
 *   - metrics.ts  (M22 Attribute Compression Ratio)
 *
 * Extracted from cveMerge.ts in Stage 5 of the metrics roadmap so the
 * compression metric can compute keys without importing the merge UI
 * machinery.
 *
 * The two-tier API:
 *   - `computePrereqKeyFromData(d)` / `computeOutcomeKeyFromData(d)` —
 *     pure functions over a plain `CveKeyData` object. Unit-testable
 *     without a Cytoscape instance.
 *   - `computePrereqKey(node)` / `computeOutcomeKey(node)` — live
 *     wrappers that read the same fields from a Cytoscape NodeSingular.
 *
 * Both keys include layer (L1/L2) and chain_depth in their suffix to
 * prevent cross-layer / cross-depth merging — two CVEs with identical
 * prerequisites but different attack-graph depth must NOT collapse.
 *
 * `formatMergeLabel` formats a key into a human-readable compound-node
 * label. Lives here so any future caller (the M22 metric, an audit
 * tool, etc.) can produce identical labels.
 */

import type { NodeSingular } from 'cytoscape';

export type MergeMode = 'none' | 'prereqs' | 'outcomes';

/**
 * Subset of a CVE node's data that the key functions read. Decouples the
 * key computation from Cytoscape so it can be unit-tested with plain
 * objects.
 */
export interface CveKeyData {
    prereqs?: { AV?: string; AC?: string; PR?: string; UI?: string } | null;
    vc_outcomes?: ReadonlyArray<readonly [string, string]> | null;
    chain_depth?: number;
    layer?: string;
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

/**
 * Live-node prereq-key. Reads the same fields off a Cytoscape node and
 * delegates to the pure helper. Behaviour identical to the original
 * `computePrereqKey` function that lived in cveMerge.ts before
 * extraction.
 */
export function computePrereqKey(node: NodeSingular): string {
    return computePrereqKeyFromData({
        prereqs: node.data('prereqs'),
        chain_depth: node.data('chain_depth'),
        layer: node.data('layer'),
    });
}

/** Live-node outcome-key. Mirror of `computePrereqKey`. */
export function computeOutcomeKey(node: NodeSingular): string {
    return computeOutcomeKeyFromData({
        vc_outcomes: node.data('vc_outcomes'),
        chain_depth: node.data('chain_depth'),
        layer: node.data('layer'),
    });
}

/**
 * Format a merge key into a readable compound-node label.
 *
 *   prereqs:  "AV:N|AC:L|PR:N|UI:N|L1|d0" → "AV:N / AC:L / PR:N / UI:N (×6)"
 *   outcomes: "AV:L,EX:Y,PR:H|L1|d0"      → "→ AV:L, EX:Y, PR:H (×3)"
 *   outcomes (no VCs): "none|L1|d0"        → "→ no VCs (×N)"
 */
export function formatMergeLabel(key: string, count: number, mode: MergeMode): string {
    // Remove layer and depth suffixes for display
    const cleanKey = key.replace(/\|L\d+\|d\d+$/, '');

    if (mode === 'prereqs') {
        return cleanKey.replace(/\|/g, ' / ') + ` (×${count})`;
    } else {
        if (cleanKey === 'none') return `→ no VCs (×${count})`;
        return '→ ' + cleanKey.replace(/,/g, ', ') + ` (×${count})`;
    }
}
