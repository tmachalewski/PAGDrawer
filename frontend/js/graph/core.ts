/**
 * Core Cytoscape graph management
 */

import { getCytoscapeStyles } from '../config/constants';
import type { Core, ElementsDefinition } from 'cytoscape';

// Declare cytoscape as global (loaded via CDN)
declare const cytoscape: (options: any) => Core;

let cy: Core | null = null;

/**
 * Get the Cytoscape instance
 */
export function getCy(): Core | null {
    return cy;
}

/**
 * Initialize Cytoscape with graph data
 */
export function initCytoscape(elements: ElementsDefinition): Core {
    cy = cytoscape({
        container: document.getElementById('cy'),
        elements: elements,
        boxSelectionEnabled: true,
        selectionType: 'additive',
        style: getCytoscapeStyles(),
        layout: { name: 'preset' },
        wheelSensitivity: 0.3,
        minZoom: 0.05,
        maxZoom: 5
    });

    return cy;
}

/**
 * Reset the graph instance
 */
export function destroyCytoscape(): void {
    if (cy) {
        cy.destroy();
        cy = null;
    }
}
