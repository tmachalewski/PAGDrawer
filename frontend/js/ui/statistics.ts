/**
 * Statistics modal — presents live graph counts, backend counts,
 * and clean attack-graph metrics with interpretation notes.
 */

import { getCy } from '../graph/core';
import { fetchStats } from '../services/api';

// Node types considered "structural artifacts" (not attack-graph steps)
const ARTIFACT_NODE_TYPES = new Set(['ATTACKER', 'COMPOUND', 'BRIDGE', 'CVE_GROUP']);

interface TypeCount {
    type: string;
    count: number;
}

/**
 * Open the statistics modal and populate all sections.
 */
export async function openStatistics(): Promise<void> {
    const modal = document.getElementById('statistics-modal');
    if (modal) modal.style.display = 'flex';

    await refreshStatistics();
}

/**
 * Close the statistics modal.
 */
export function closeStatistics(): void {
    const modal = document.getElementById('statistics-modal');
    if (modal) modal.style.display = 'none';
}

/**
 * Refresh all statistics sections.
 */
export async function refreshStatistics(): Promise<void> {
    populateLiveStats();
    await populateBackendStats();
    populateCleanMetrics();
}

/**
 * Populate live stats from the current Cytoscape graph.
 */
function populateLiveStats(): void {
    const cy = getCy();
    if (!cy) return;

    const visibleNodes = cy.nodes().filter(n => !n.hasClass('exploit-hidden'));
    const visibleEdges = cy.edges().filter(e => !e.hasClass('exploit-hidden'));

    setText('stats-live-nodes', String(visibleNodes.length));
    setText('stats-live-edges', String(visibleEdges.length));

    // Per-type node breakdown
    const nodeCounts: Record<string, number> = {};
    visibleNodes.forEach(n => {
        const t = (n.data('type') as string) || 'unknown';
        nodeCounts[t] = (nodeCounts[t] || 0) + 1;
    });
    renderTypeTable('stats-node-table', nodeCounts);

    // Per-type edge breakdown
    const edgeCounts: Record<string, number> = {};
    visibleEdges.forEach(e => {
        const t = (e.data('type') as string) || 'unknown';
        edgeCounts[t] = (edgeCounts[t] || 0) + 1;
    });
    renderTypeTable('stats-edge-table', edgeCounts);
}

/**
 * Populate backend stats from /api/stats.
 */
async function populateBackendStats(): Promise<void> {
    try {
        const stats = await fetchStats();
        setText('stats-backend-nodes', String(stats.total_nodes));
        setText('stats-backend-edges', String(stats.total_edges));
    } catch (err) {
        console.error('Failed to fetch backend stats:', err);
        setText('stats-backend-nodes', '?');
        setText('stats-backend-edges', '?');
    }
}

/**
 * Compute and display "clean" attack graph metrics that strip structural
 * artifacts and frontend-synthetic elements.
 */
function populateCleanMetrics(): void {
    const cy = getCy();
    if (!cy) return;

    const visibleNodes = cy.nodes().filter(n => !n.hasClass('exploit-hidden'));
    const visibleEdges = cy.edges().filter(e => !e.hasClass('exploit-hidden'));

    // Nodes: strip ATTACKER, COMPOUND, BRIDGE, CVE_GROUP
    const cleanNodes = visibleNodes.filter(n => {
        const t = (n.data('type') as string) || '';
        return !ARTIFACT_NODE_TYPES.has(t);
    }).length;

    // Edges: strip synthetic (from outcomes merge) and edges touching artifacts
    const cleanEdges = visibleEdges.filter(ele => {
        const e = ele as any; // EdgeSingular — filter returns the parent abstract type
        if (e.data('synthetic')) return false;
        const srcType = (e.source().data('type') as string) || '';
        const tgtType = (e.target().data('type') as string) || '';
        return !ARTIFACT_NODE_TYPES.has(srcType) && !ARTIFACT_NODE_TYPES.has(tgtType);
    }).length;

    // Unique CVE IDs (strip :dN suffix and @... context to see how many unique CVEs)
    const uniqueCVEs = new Set<string>();
    visibleNodes.forEach(n => {
        if (n.data('type') === 'CVE') {
            const id = n.id();
            // Extract base CVE ID (before :d or @)
            const base = id.replace(/[:@].*$/, '');
            uniqueCVEs.add(base);
        }
    });

    // Initial-state VCs (the UI/AC/AV/PR in ATTACKER_BOX)
    const initialStateVCs = visibleNodes.filter(n =>
        n.data('type') === 'VC' && n.data('is_initial')
    ).length;

    const rows: TypeCount[] = [
        { type: 'Attack graph nodes (excl. artifacts)', count: cleanNodes },
        { type: 'Attack graph edges (excl. artifacts, synthetic)', count: cleanEdges },
        { type: 'Unique CVE IDs', count: uniqueCVEs.size },
        { type: 'Initial-state VCs (in Initial State box)', count: initialStateVCs },
    ];

    const tableBody = document.querySelector('#stats-clean-table tbody');
    if (!tableBody) return;
    tableBody.innerHTML = '';
    rows.forEach(row => {
        const tr = document.createElement('tr');
        const td1 = document.createElement('td');
        td1.textContent = row.type;
        const td2 = document.createElement('td');
        td2.textContent = String(row.count);
        tr.appendChild(td1);
        tr.appendChild(td2);
        tableBody.appendChild(tr);
    });
}

/**
 * Render a sorted type-count table.
 */
function renderTypeTable(tableId: string, counts: Record<string, number>): void {
    const tableBody = document.querySelector(`#${tableId} tbody`);
    if (!tableBody) return;
    tableBody.innerHTML = '';

    const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    entries.forEach(([type, count]) => {
        const tr = document.createElement('tr');
        const td1 = document.createElement('td');
        td1.textContent = type;
        const td2 = document.createElement('td');
        td2.textContent = String(count);
        tr.appendChild(td1);
        tr.appendChild(td2);
        tableBody.appendChild(tr);
    });
}

function setText(id: string, value: string): void {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

// Expose globals for onclick handlers in index.html
(window as any).openStatistics = openStatistics;
(window as any).closeStatistics = closeStatistics;
