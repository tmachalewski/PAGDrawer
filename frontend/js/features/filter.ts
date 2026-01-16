/**
 * Node type filtering and visibility
 */

import { getCy } from '../graph/core';
import type { EdgeSingular, ElementDefinition } from 'cytoscape';

// Track hidden node types and their elements
const hiddenTypes: Set<string> = new Set();

interface HiddenTypeData {
    nodes: ElementDefinition[];
    edges: ElementDefinition[];
}
const hiddenByType: Map<string, HiddenTypeData> = new Map();
const typeBridgeEdges: Map<string, EdgeSingular[]> = new Map();


/**
 * Setup filter button event listeners
 */
export function setupFilterButtons(): void {
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', function (this: HTMLElement) {
            const type = this.dataset.type || 'all';
            filterByType(type);

            // Update active button
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
        });
    });

    // Setup visibility toggle buttons
    document.querySelectorAll('.visibility-toggle').forEach(btn => {
        btn.addEventListener('click', function (this: HTMLElement) {
            const type = this.dataset.type;
            if (!type) return;

            toggleTypeVisibility(type);

            // Update button state
            this.classList.toggle('hidden');
        });
    });
}

/**
 * Toggle visibility of a node type - removes nodes and creates bridge edges
 */
export function toggleTypeVisibility(type: string): void {
    const cy = getCy();
    if (!cy) return;

    if (hiddenTypes.has(type)) {
        // Show nodes of this type - restore them
        showNodeType(type);
    } else {
        // Hide nodes of this type - remove them and create bridges
        hideNodeType(type);
    }
}

/**
 * Hide all nodes of a type, creating bridge edges
 */
function hideNodeType(type: string): void {
    const cy = getCy();
    if (!cy) return;

    hiddenTypes.add(type);
    const nodesToHide = cy.nodes(`[type="${type}"]`);
    const storedNodes: ElementDefinition[] = [];
    const storedEdges: ElementDefinition[] = [];
    const bridges: EdgeSingular[] = [];

    nodesToHide.forEach(node => {
        // Get predecessors and successors (only visible ones)
        const incomers = node.incomers('node').filter(n => !hiddenTypes.has(n.data('type')));
        const outgoers = node.outgoers('node').filter(n => !hiddenTypes.has(n.data('type')));

        // Create bridge edges from predecessors to successors
        incomers.forEach(pred => {
            outgoers.forEach(succ => {
                const bridgeId = `typebridge_${type}_${pred.id()}_${succ.id()}`;
                // Check if bridge already exists
                if (cy.getElementById(bridgeId).length === 0) {
                    const bridgeEdge = cy.add({
                        group: 'edges',
                        data: {
                            id: bridgeId,
                            source: pred.id(),
                            target: succ.id(),
                            type: 'BRIDGE',
                            isBridge: true,
                            bridgeForType: type
                        }
                    }) as EdgeSingular;
                    bridges.push(bridgeEdge);
                }
            });
        });

        // Store node data
        storedNodes.push(node.json() as ElementDefinition);

        // Store and remove edges (excluding bridges)
        const connected = node.connectedEdges().filter(e => !e.data('isBridge'));
        connected.forEach(edge => {
            storedEdges.push(edge.json() as ElementDefinition);
        });
    });

    // Store data for restoration
    hiddenByType.set(type, { nodes: storedNodes, edges: storedEdges });
    typeBridgeEdges.set(type, bridges);

    // Remove nodes (edges are removed automatically)
    nodesToHide.remove();
}

/**
 * Show all nodes of a type, removing bridge edges
 */
function showNodeType(type: string): void {
    const cy = getCy();
    if (!cy) return;

    hiddenTypes.delete(type);

    // Remove bridge edges for this type
    const bridges = typeBridgeEdges.get(type) || [];
    bridges.forEach(edge => {
        if (edge.inside()) edge.remove();
    });
    typeBridgeEdges.delete(type);

    // Also remove by selector in case any were missed
    cy.edges(`[bridgeForType="${type}"]`).remove();

    // Restore nodes
    const data = hiddenByType.get(type);
    if (data) {
        // First restore nodes
        data.nodes.forEach(nodeData => {
            if (cy.getElementById(nodeData.data?.id as string).length === 0) {
                cy.add(nodeData);
            }
        });

        // Then restore edges (only if both ends exist and are not hidden)
        data.edges.forEach(edgeData => {
            const sourceId = edgeData.data?.source as string;
            const targetId = edgeData.data?.target as string;
            const edgeId = edgeData.data?.id as string;

            const sourceNode = cy.getElementById(sourceId);
            const targetNode = cy.getElementById(targetId);

            if (sourceNode.length && targetNode.length) {
                const sourceType = sourceNode.data('type');
                const targetType = targetNode.data('type');

                // Only restore if both ends are visible
                if (!hiddenTypes.has(sourceType) && !hiddenTypes.has(targetType)) {
                    if (cy.getElementById(edgeId).length === 0) {
                        cy.add(edgeData);
                    }
                }
            }
        });

        hiddenByType.delete(type);
    }
}

/**
 * Get currently hidden types
 */
export function getHiddenTypes(): Set<string> {
    return new Set(hiddenTypes);
}

/**
 * Reapply hidden types after graph rebuild
 * Call this after reinitializing Cytoscape to preserve visibility state
 */
export function reapplyHiddenTypes(): void {
    const cy = getCy();
    if (!cy) return;

    // Get types that should be hidden
    const typesToHide = Array.from(hiddenTypes);

    if (typesToHide.length === 0) return;

    // Clear stored data (will be repopulated)
    hiddenByType.clear();
    typeBridgeEdges.clear();
    hiddenTypes.clear();

    // Re-hide each type
    typesToHide.forEach(type => {
        hideNodeType(type);
    });
}

/**
 * Reset all visibility (show all types)
 * Uses two-pass restoration to ensure edges between restored types are preserved
 */
export function resetVisibility(): void {
    const cy = getCy();
    if (!cy) return;

    const typesToShow = Array.from(hiddenTypes);

    // First pass: remove all bridge edges and restore all nodes
    typesToShow.forEach(type => {
        // Remove bridge edges for this type
        const bridges = typeBridgeEdges.get(type) || [];
        bridges.forEach(edge => {
            if (edge.inside()) edge.remove();
        });
        cy.edges(`[bridgeForType="${type}"]`).remove();

        // Restore nodes
        const data = hiddenByType.get(type);
        if (data) {
            data.nodes.forEach(nodeData => {
                if (cy.getElementById(nodeData.data?.id as string).length === 0) {
                    cy.add(nodeData);
                }
            });
        }
    });

    // Clear hidden types BEFORE second pass so edge restoration works
    hiddenTypes.clear();

    // Second pass: restore all edges (now all nodes exist and no types are hidden)
    typesToShow.forEach(type => {
        const data = hiddenByType.get(type);
        if (data) {
            data.edges.forEach(edgeData => {
                const sourceId = edgeData.data?.source as string;
                const targetId = edgeData.data?.target as string;
                const edgeId = edgeData.data?.id as string;

                const sourceNode = cy.getElementById(sourceId);
                const targetNode = cy.getElementById(targetId);

                if (sourceNode.length && targetNode.length) {
                    if (cy.getElementById(edgeId).length === 0) {
                        cy.add(edgeData);
                    }
                }
            });
        }
    });

    hiddenByType.clear();
    typeBridgeEdges.clear();

    // Reset toggle button states
    document.querySelectorAll('.visibility-toggle').forEach(btn => {
        btn.classList.remove('hidden');
    });
}

/**
 * Filter graph by node type - SELECT nodes of type instead of hiding others
 * Preserves unreachable styling for dimmed nodes
 */
export function filterByType(type: string): void {
    const cy = getCy();
    if (!cy) return;

    // Deselect all first
    cy.elements().unselect();
    cy.elements().removeClass('faded faded-unreachable');

    if (type === 'all') {
        // Show all nodes - unreachable styling is preserved automatically
        return;
    }

    // Select nodes of this type
    const targetNodes = cy.nodes(`[type="${type}"]`);
    targetNodes.select();

    // Fade unselected nodes, but preserve unreachable distinction
    cy.elements().forEach(ele => {
        if (!targetNodes.contains(ele) && !targetNodes.connectedEdges().contains(ele)) {
            // Add faded class, but unreachable nodes stay visually distinct
            if (ele.hasClass('unreachable')) {
                // Keep unreachable styling (already dimmed)
                ele.addClass('faded-unreachable');
            } else {
                ele.addClass('faded');
            }
        }
    });
}
