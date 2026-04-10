/**
 * Node type filtering and visibility
 */

import { getCy } from '../graph/core';
import { edgeColors } from '../config/constants';
import type { EdgeSingular, ElementDefinition } from 'cytoscape';

// Track hidden node types and their elements
const hiddenTypes: Set<string> = new Set();

interface HiddenTypeData {
    nodes: ElementDefinition[];
    edges: ElementDefinition[];
}
const hiddenByType: Map<string, HiddenTypeData> = new Map();
const typeBridgeEdges: Map<string, EdgeSingular[]> = new Map();

// Global edge storage - prevents duplicates when multiple types are hidden
const globalHiddenEdges: Map<string, ElementDefinition> = new Map();

/**
 * Compute a bright averaged color from hidden edge types
 */
function computeBridgeColor(edgeTypes: string[]): string {
    if (edgeTypes.length === 0) {
        return '#00ffff'; // Default cyan for bridges
    }

    // Parse hex color to RGB
    const hexToRgb = (hex: string): [number, number, number] => {
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return result
            ? [parseInt(result[1], 16), parseInt(result[2], 16), parseInt(result[3], 16)]
            : [0, 255, 255]; // fallback cyan
    };

    // Average the colors
    let r = 0, g = 0, b = 0;
    let count = 0;

    edgeTypes.forEach(type => {
        const color = edgeColors[type];
        if (color) {
            const [cr, cg, cb] = hexToRgb(color);
            r += cr;
            g += cg;
            b += cb;
            count++;
        }
    });

    if (count === 0) {
        return '#00ffff';
    }

    r = Math.round(r / count);
    g = Math.round(g / count);
    b = Math.round(b / count);

    // Brighten the color (push towards white while preserving hue)
    const brightenFactor = 0.4; // 0 = no change, 1 = pure white
    r = Math.round(r + (255 - r) * brightenFactor);
    g = Math.round(g + (255 - g) * brightenFactor);
    b = Math.round(b + (255 - b) * brightenFactor);

    // Also boost saturation slightly by pushing away from gray
    const gray = (r + g + b) / 3;
    const saturationBoost = 1.2;
    r = Math.min(255, Math.round(gray + (r - gray) * saturationBoost));
    g = Math.min(255, Math.round(gray + (g - gray) * saturationBoost));
    b = Math.min(255, Math.round(gray + (b - gray) * saturationBoost));

    return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
}


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
                    // Collect edge types that this bridge represents
                    const hiddenEdgeTypes: string[] = [];
                    node.connectedEdges().forEach(edge => {
                        if (!edge.data('isBridge')) {
                            const edgeType = edge.data('type');
                            if (edgeType && !hiddenEdgeTypes.includes(edgeType)) {
                                hiddenEdgeTypes.push(edgeType);
                            }
                        }
                    });

                    // Compute averaged bright color from hidden edge types
                    const bridgeColor = computeBridgeColor(hiddenEdgeTypes);

                    const bridgeEdge = cy.add({
                        group: 'edges',
                        data: {
                            id: bridgeId,
                            source: pred.id(),
                            target: succ.id(),
                            type: 'BRIDGE',
                            isBridge: true,
                            bridgeForType: type,
                            hiddenEdgeTypes: hiddenEdgeTypes,
                            bridgeColor: bridgeColor
                        }
                    }) as EdgeSingular;
                    bridges.push(bridgeEdge);
                }
            });
        });

        // Store node data
        storedNodes.push(node.json() as ElementDefinition);

        // Store and remove edges (excluding bridges) - use global storage to prevent duplicates
        const connected = node.connectedEdges().filter(e => !e.data('isBridge'));
        connected.forEach(edge => {
            const edgeId = edge.id();
            // Only store if not already globally stored
            if (!globalHiddenEdges.has(edgeId)) {
                globalHiddenEdges.set(edgeId, edge.json() as ElementDefinition);
            }
            // Still track per-type for bridge edge management
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
 *
 * Uses a full restore-then-rehide approach to ensure bridges are
 * correctly recreated when other types remain hidden. This avoids
 * the problem where restored nodes become dead ends because their
 * edges to still-hidden types can't be restored and no bridges are
 * created to bypass them.
 */
function showNodeType(type: string): void {
    const cy = getCy();
    if (!cy) return;

    // Determine which types should remain hidden after showing this one
    const typesToRemainHidden = new Set(hiddenTypes);
    typesToRemainHidden.delete(type);

    // Phase 1: Restore everything (all nodes, all edges, remove all bridges)
    cy.edges('[isBridge]').remove();

    // Restore all hidden nodes
    hiddenByType.forEach((data) => {
        data.nodes.forEach(nodeData => {
            if (cy.getElementById(nodeData.data?.id as string).length === 0) {
                cy.add(nodeData);
            }
        });
    });

    // Clear hiddenTypes before restoring edges so all types are "visible"
    hiddenTypes.clear();

    // Restore all globally hidden edges
    globalHiddenEdges.forEach((edgeData, edgeId) => {
        const sourceId = edgeData.data?.source as string;
        const targetId = edgeData.data?.target as string;
        const sourceNode = cy.getElementById(sourceId);
        const targetNode = cy.getElementById(targetId);
        if (sourceNode.length && targetNode.length) {
            if (cy.getElementById(edgeId).length === 0) {
                cy.add(edgeData);
            }
        }
    });

    // Clear all storage
    hiddenByType.clear();
    typeBridgeEdges.clear();
    globalHiddenEdges.clear();

    // Phase 2: Re-hide the types that should remain hidden
    // hideNodeType creates correct bridges based on current visibility
    typesToRemainHidden.forEach(t => {
        hideNodeType(t);
    });
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

    // Second pass: restore all edges from global storage (now all nodes exist)
    globalHiddenEdges.forEach((edgeData, edgeId) => {
        const sourceId = edgeData.data?.source as string;
        const targetId = edgeData.data?.target as string;

        const sourceNode = cy.getElementById(sourceId);
        const targetNode = cy.getElementById(targetId);

        if (sourceNode.length && targetNode.length) {
            if (cy.getElementById(edgeId).length === 0) {
                cy.add(edgeData);
            }
        }
    });

    // Clear all storage
    hiddenByType.clear();
    typeBridgeEdges.clear();
    globalHiddenEdges.clear();

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
