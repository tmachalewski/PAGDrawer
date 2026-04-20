/**
 * Sidebar UI updates
 */

import type { Stats } from '../types';
import { getCy } from '../graph/core';

/**
 * Update stats panel with graph statistics from backend.
 * Total counts now live in the Statistics modal (see ui/statistics.ts);
 * this is kept for API compatibility but only refreshes per-type counts.
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function updateStats(_stats: Stats): void {
    updateLiveStats();
}

/**
 * Update per-type node counts next to sliders in the settings modal.
 * Total counts live in the Statistics modal.
 */
export function updateLiveStats(): void {
    const cy = getCy();
    if (!cy) return;

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
