/**
 * Node type filtering
 */

import { getCy } from '../graph/core';


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
