/**
 * CVE node merging via Cytoscape compound (parent) nodes.
 *
 * Groups CVE nodes by prerequisites or outcomes when CWE+TI are hidden.
 * Merge is purely visual — original node identity preserved as children
 * of compound parent nodes.
 */

import { getCy } from '../graph/core';
import { runLayout } from '../graph/layout';
import {
    computePrereqKey,
    computeOutcomeKey,
    formatMergeLabel,
    type MergeMode,
} from './mergeKeys';

// Re-export for back-compat: callers that imported these from cveMerge.ts
// continue to work. New callers should import directly from `./mergeKeys`.
export { computePrereqKey, computeOutcomeKey, formatMergeLabel };
export type { MergeMode };

// --- State ---
let currentMergeMode: MergeMode = 'none';
let mergeParentIds: string[] = [];
let syntheticEdgeIds: string[] = [];
let hiddenEdgeIds: string[] = [];
let toastShown = false;

// Injected dependency to avoid circular import with filter.ts
let _getHiddenTypes: () => Set<string> = () => new Set();

/**
 * Inject the getHiddenTypes function from filter.ts.
 * Called once during init to break the circular dependency.
 */
export function injectGetHiddenTypes(fn: () => Set<string>): void {
    _getHiddenTypes = fn;
}

/**
 * Check if merge is available (CWE + TI both hidden)
 */
export function isMergeAvailable(): boolean {
    const hidden = _getHiddenTypes();
    return hidden.has('CWE') && hidden.has('TI');
}

/**
 * Get current merge mode
 */
export function getMergeMode(): MergeMode {
    return currentMergeMode;
}

/**
 * Update merge button visibility based on hidden types.
 * Shows toast the first time merge becomes available.
 */
export function updateMergeButtonVisibility(): void {
    const btn = document.getElementById('cve-merge-btn') as HTMLButtonElement | null;
    if (!btn) return;

    const wasDisabled = btn.disabled;

    if (isMergeAvailable()) {
        btn.disabled = false;
        btn.classList.remove('disabled');
        btn.title = 'Merge CVE nodes';

        // Show toast the first time merge becomes available
        if (wasDisabled && !toastShown) {
            toastShown = true;
            showMergeToast();
        }
    } else {
        btn.disabled = true;
        btn.classList.add('disabled');
        btn.title = 'Hide CWE and TI nodes to enable merging';
        // Auto-disable merge if conditions no longer met
        if (currentMergeMode !== 'none') {
            setMergeMode('none');
        }
    }
}

/**
 * Set merge mode and apply/remove compound nodes
 */
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

/**
 * Apply merge — create compound parent nodes and reparent CVEs into them.
 * CVEs remain hoverable inside the compound box.
 */
export function applyMerge(): void {
    removeMerge();
    const cy = getCy();
    if (!cy || currentMergeMode === 'none') return;

    // Only merge CVEs that are actually rendered. Exploit-Paths filter
    // adds `exploit-hidden` (display:none) to CVEs off any EX:Y path; if
    // we merged those too, the resulting compound would have children
    // that are all invisible and dagre would strand it at (0,0).
    const cveNodes = cy.nodes('[type="CVE"]').filter(n => !n.hasClass('exploit-hidden'));
    const groups: Map<string, string[]> = new Map();

    // Group CVEs by computed key (layer-aware)
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
                label: formatMergeLabel(key, nodeIds.length, currentMergeMode),
                mergeKey: key,
                mergeMode: currentMergeMode
            }
        });
        mergeParentIds.push(parentId);

        // Move children into compound
        const nodeIdSet = new Set(nodeIds);
        nodeIds.forEach(id => {
            cy.getElementById(id).move({ parent: parentId });
        });

        // In outcomes mode, consolidate edges into the compound parent
        if (currentMergeMode === 'outcomes') {
            const seenEdges = new Set<string>();

            nodeIds.forEach(id => {
                const node = cy.getElementById(id);
                node.connectedEdges().forEach(edge => {
                    const srcId = edge.source().id();
                    const tgtId = edge.target().id();
                    const isSource = srcId === id;
                    const otherId = isSource ? tgtId : srcId;

                    // Skip edges between nodes in the same group
                    if (nodeIdSet.has(otherId)) return;

                    const edgeType = edge.data('type') || '';
                    const edgeKey = `${isSource ? 'out' : 'in'}|${otherId}|${edgeType}`;

                    // Hide original edge
                    edge.style('display', 'none');
                    hiddenEdgeIds.push(edge.id());

                    // Create deduped synthetic edge from/to compound parent
                    if (seenEdges.has(edgeKey)) return;
                    seenEdges.add(edgeKey);

                    const synId = `syn_${parentId}_${edgeKey}`;
                    cy.add({
                        group: 'edges',
                        data: {
                            id: synId,
                            source: isSource ? parentId : otherId,
                            target: isSource ? otherId : parentId,
                            type: edgeType,
                            synthetic: true
                        }
                    });
                    syntheticEdgeIds.push(synId);
                });
            });
        }
    });

    runLayout();
}

/**
 * Remove merge — dissolve compound nodes, move children back to root
 */
export function removeMerge(): void {
    const cy = getCy();
    if (!cy) return;

    const hadMerge = mergeParentIds.length > 0;

    // Remove synthetic edges
    syntheticEdgeIds.forEach(id => {
        const edge = cy.getElementById(id);
        if (edge.length) edge.remove();
    });
    syntheticEdgeIds = [];

    // Restore hidden edges
    hiddenEdgeIds.forEach(id => {
        const edge = cy.getElementById(id);
        if (edge.length) edge.style('display', 'element');
    });
    hiddenEdgeIds = [];

    // Dissolve compound nodes
    mergeParentIds.forEach(parentId => {
        const parent = cy.getElementById(parentId);
        if (parent.length) {
            parent.children().move({ parent: null });
            parent.remove();
        }
    });
    mergeParentIds = [];

    if (hadMerge) {
        runLayout();
    }
}

/**
 * Reset merge state (called on graph rebuild)
 */
export function resetMerge(): void {
    currentMergeMode = 'none';
    mergeParentIds = [];
    syntheticEdgeIds = [];
    hiddenEdgeIds = [];
    const btn = document.getElementById('cve-merge-btn');
    if (btn) {
        btn.classList.remove('active');
    }
    updateMergeButtonVisibility();
}

/**
 * Setup merge button and popover event handlers
 */
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

/**
 * Toggle merge popover visibility
 */
function togglePopover(): void {
    const popover = document.getElementById('merge-popover');
    if (!popover) return;

    if (popover.style.display === 'none' || !popover.style.display) {
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

/**
 * Hide merge popover
 */
function hidePopover(): void {
    const popover = document.getElementById('merge-popover');
    if (popover) popover.style.display = 'none';
}

/**
 * Show a one-time toast notification when merge becomes available
 */
function showMergeToast(): void {
    const toast = document.createElement('div');
    toast.className = 'merge-toast';
    toast.textContent = 'CVE merging now available \u2014 click \u229e on CVE row';
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
