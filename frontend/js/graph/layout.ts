/**
 * Graph layout algorithms
 */

import { getCy } from './core';


let currentLayout = 'dagre';

interface ColumnPositions {
    [nodeId: string]: { rank: number };
}

/**
 * Change the current layout
 */
export function changeLayout(layoutName: string): void {
    currentLayout = layoutName;
    runLayout();
}

/**
 * Get column positions for dagre layout
 */
export function getColumnPositions(): ColumnPositions {
    const cy = getCy();
    if (!cy) return {};

    const columns: Record<string, number> = {
        ATTACKER: 0,
        HOST: 1,
        CPE: 2,
        CVE: 3,
        CWE: 4,
        TI: 5,
        VC: 6
    };

    // Special nodes
    const specialPositions: ColumnPositions = {};

    cy.nodes().forEach(node => {
        const type = node.data('type') as string;
        const id = node.id();

        if (type === 'BRIDGE' || node.data('is_phase_separator')) {
            specialPositions[id] = { rank: 7 };
        } else if (type === 'COMPOUND') {
            specialPositions[id] = { rank: 0 };
        } else if (columns[type] !== undefined) {
            specialPositions[id] = { rank: columns[type] };
        }
    });

    return specialPositions;
}

/**
 * Run the current layout algorithm
 * Only layouts visible elements (excludes exploit-hidden and filtered elements)
 */
export function runLayout(): void {
    const cy = getCy();
    if (!cy) return;

    // Get only visible elements (exclude hidden by exploit paths or filters)
    const visibleElements = cy.elements().not('.exploit-hidden').not('.filtered');

    let layoutConfig: any;

    if (currentLayout === 'dagre') {
        layoutConfig = {
            name: 'dagre',
            rankDir: 'LR',
            nodeSep: 50,
            rankSep: 100,
            edgeSep: 20,
            ranker: 'tight-tree',
            animate: true,
            animationDuration: 500
        };
    } else if (currentLayout === 'breadthfirst') {
        layoutConfig = {
            name: 'breadthfirst',
            directed: true,
            spacingFactor: 1.5,
            animate: true,
            animationDuration: 500,
            roots: visibleElements.nodes('[type="ATTACKER"]')
        };
    } else if (currentLayout === 'cose') {
        layoutConfig = {
            name: 'cose',
            animate: true,
            animationDuration: 500,
            nodeRepulsion: 8000,
            idealEdgeLength: 80
        };
    } else if (currentLayout === 'circle') {
        layoutConfig = {
            name: 'circle',
            animate: true,
            animationDuration: 500
        };
    } else {
        layoutConfig = { name: currentLayout, animate: true };
    }

    // Run layout only on visible elements
    visibleElements.layout(layoutConfig).run();
}

/**
 * Fit the graph to the viewport
 */
export function fitView(): void {
    const cy = getCy();
    if (cy) {
        cy.fit(undefined, 50);
    }
}

/**
 * Get current layout name
 */
export function getCurrentLayout(): string {
    return currentLayout;
}
