/**
 * Sidebar UI updates
 */

import type { Stats } from '../types';

/**
 * Update stats panel with graph statistics
 */
export function updateStats(stats: Stats): void {
    const nodesEl = document.getElementById('total-nodes');
    const edgesEl = document.getElementById('total-edges');
    if (nodesEl) nodesEl.textContent = String(stats.total_nodes);
    if (edgesEl) edgesEl.textContent = String(stats.total_edges);
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
