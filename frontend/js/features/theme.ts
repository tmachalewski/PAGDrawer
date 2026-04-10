/**
 * Theme toggle - dark/light mode
 *
 * Light theme is designed for academic paper image exports:
 * white background, high-contrast colors, dark text outlines.
 */

import { getCy } from '../graph/core';

let currentTheme: 'dark' | 'light' = 'dark';

/** Light-mode node colors — higher contrast for print */
const lightNodeColors: Record<string, string> = {
    HOST: '#cc2222',
    CPE: '#cc6600',
    CVE: '#b8860b',
    CWE: '#1a8a1a',
    TI: '#0077aa',
    VC: '#4a44cc',
    ATTACKER: '#cc0055',
    BRIDGE: '#00aa55'
};

/** Light-mode edge colors */
const lightEdgeColors: Record<string, string> = {
    RUNS: '#cc2222',
    HAS_VULN: '#cc6600',
    IS_INSTANCE_OF: '#1a8a1a',
    HAS_IMPACT: '#0077aa',
    CONNECTED_TO: '#666666',
    ALLOWS_EXPLOIT: '#4a44cc',
    YIELDS_STATE: '#7733aa',
    LEADS_TO: '#7733aa',
    ENABLES: '#008888',
    PIVOTS_TO: '#cc7700',
    BRIDGE: '#008888',
    ATTACKS_FROM: '#cc0055',
    HAS_STATE: '#cc0055',
    CAN_REACH: '#cc5500',
    ENTERS_NETWORK: '#00aa55'
};

export function getTheme(): 'dark' | 'light' {
    return currentTheme;
}

export function toggleTheme(): void {
    currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
    applyTheme();
}

function applyTheme(): void {
    const body = document.body;
    const cy = getCy();

    if (currentTheme === 'light') {
        body.classList.add('light-theme');
    } else {
        body.classList.remove('light-theme');
    }

    if (!cy) return;

    // Update Cytoscape renderer background
    const container = cy.container();
    if (container) {
        container.style.background = currentTheme === 'light' ? '#ffffff' : '';
    }

    // Update node styles
    cy.nodes().forEach(node => {
        const type = node.data('type');
        if (currentTheme === 'light' && lightNodeColors[type]) {
            node.style('background-color', lightNodeColors[type]);
            node.style('text-outline-color', '#ffffff');
            node.style('text-outline-width', 1);
            node.style('color', '#111111');
        } else {
            // Reset to defaults (handled by stylesheet)
            node.removeStyle('background-color');
            node.removeStyle('text-outline-color');
            node.removeStyle('text-outline-width');
            node.removeStyle('color');
        }
    });

    // Update edge styles
    cy.edges().forEach(edge => {
        const type = edge.data('type');
        if (currentTheme === 'light' && lightEdgeColors[type]) {
            edge.style('line-color', lightEdgeColors[type]);
            edge.style('target-arrow-color', lightEdgeColors[type]);
        } else {
            edge.removeStyle('line-color');
            edge.removeStyle('target-arrow-color');
        }
    });

    // Update theme toggle button text
    const btn = document.getElementById('theme-toggle-btn');
    if (btn) {
        btn.textContent = currentTheme === 'light' ? '🌙 Dark' : '☀️ Light';
    }
}
