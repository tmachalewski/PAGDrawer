/**
 * Sidebar UI updates
 */

import type { Stats } from '../types';
import { getCy } from '../graph/core';

/**
 * Update stats panel with graph statistics from backend
 */
export function updateStats(stats: Stats): void {
    const nodesEl = document.getElementById('total-nodes');
    const edgesEl = document.getElementById('total-edges');
    if (nodesEl) nodesEl.textContent = String(stats.total_nodes);
    if (edgesEl) edgesEl.textContent = String(stats.total_edges);
}

/**
 * Update stats panel with LIVE graph statistics from Cytoscape
 * This reflects current visible state including visibility toggles and filters
 */
export function updateLiveStats(): void {
    const cy = getCy();
    if (!cy) return;

    const nodesEl = document.getElementById('total-nodes');
    const edgesEl = document.getElementById('total-edges');

    // Count visible nodes (excluding exploit-hidden)
    const visibleNodes = cy.nodes().filter(n => !n.hasClass('exploit-hidden')).length;
    // Count visible edges (excluding exploit-hidden)
    const visibleEdges = cy.edges().filter(e => !e.hasClass('exploit-hidden')).length;

    if (nodesEl) nodesEl.textContent = String(visibleNodes);
    if (edgesEl) edgesEl.textContent = String(visibleEdges);

    // Update per-type counts in settings modal slider labels
    const types = ['CPE', 'CVE', 'CWE', 'TI', 'VC'];
    types.forEach(type => {
        const countEl = document.getElementById(`count-${type}`);
        if (countEl) {
            const count = cy.nodes().filter(n => n.data('type') === type && !n.hasClass('exploit-hidden')).length;
            countEl.textContent = `(${count})`;
        }
    });
}

/**
 * Show loading state
 */
export function showLoading(): void {
    const loadingEl = document.getElementById('loading-overlay');
    if (loadingEl) loadingEl.style.display = 'block';
}

/**
 * Hide loading state
 */
export function hideLoading(): void {
    const loadingEl = document.getElementById('loading-overlay');
    if (loadingEl) loadingEl.style.display = 'none';
}

/**
 * Show error message
 */
export function showError(message: string): void {
    const loadingEl = document.querySelector('.loading');
    if (loadingEl) loadingEl.textContent = message;
}
