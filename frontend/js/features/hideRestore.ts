/**
 * Hide/Restore functionality with bridge edges
 */

import { getCy } from '../graph/core';
import { runLayout } from '../graph/layout';
import { resetVisibility } from './filter';
import type { EdgeSingular, ElementDefinition } from 'cytoscape';

interface HiddenItem {
    node: ElementDefinition;
    edges: ElementDefinition[];
}

let hiddenElements: HiddenItem[] = [];
let bridgeEdges: EdgeSingular[] = [];

/**
 * Hide selected nodes, creating bridge edges to maintain connectivity
 */
export function hideSelectedNodes(): void {
    const cy = getCy();
    if (!cy) return;

    const selected = cy.nodes(':selected');
    if (selected.length === 0) {
        alert('Select nodes first (click or Shift+drag to box-select)');
        return;
    }

    selected.forEach(node => {
        const incomers = node.incomers('node');
        const outgoers = node.outgoers('node');

        // Create bridge edges from predecessors to successors
        incomers.forEach(pred => {
            outgoers.forEach(succ => {
                const existingEdge = cy.edges(`[source = "${pred.id()}"][target = "${succ.id()}"]`);
                if (existingEdge.length === 0) {
                    const bridgeEdge = cy.add({
                        group: 'edges',
                        data: {
                            id: `bridge_${pred.id()}_${succ.id()}_${Date.now()}`,
                            source: pred.id(),
                            target: succ.id(),
                            type: 'BRIDGE',
                            isBridge: true
                        }
                    }) as EdgeSingular;
                    bridgeEdges.push(bridgeEdge);
                }
            });
        });

        // Store and remove the node and its edges
        const connected = node.connectedEdges();
        // Filter out bridge edges - we don't want to restore those
        const originalEdges = connected.filter(e => !e.data('isBridge'));
        hiddenElements.push({
            node: node.json() as ElementDefinition,
            edges: originalEdges.map(e => e.json() as ElementDefinition)
        });
        connected.remove();
        node.remove();
    });

    runLayout();
}

/**
 * Restore all hidden nodes and their edges
 */
export function restoreAllNodes(): void {
    const cy = getCy();
    if (!cy) return;

    // Remove bridge edges - both from stored array and by selector
    bridgeEdges.forEach(edge => {
        if (edge.inside()) edge.remove();
    });
    bridgeEdges = [];

    // Also remove any edges marked as bridge that might still exist
    cy.edges('[?isBridge]').remove();

    // First pass: restore ALL hidden nodes
    hiddenElements.forEach(item => {
        cy.add(item.node);
    });

    // Second pass: restore ALL edges (now all nodes exist)
    hiddenElements.forEach(item => {
        item.edges.forEach(edgeData => {
            if (cy.getElementById(edgeData.data?.source as string).length &&
                cy.getElementById(edgeData.data?.target as string).length) {
                if (!cy.getElementById(edgeData.data?.id as string).length) {
                    cy.add(edgeData);
                }
            }
        });
    });

    hiddenElements = [];

    // Also reset visibility toggles
    resetVisibility();

    runLayout();
}

/**
 * Get count of hidden elements
 */
export function getHiddenCount(): number {
    return hiddenElements.length;
}
