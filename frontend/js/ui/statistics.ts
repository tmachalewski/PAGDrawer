/**
 * Statistics modal — presents live graph counts, backend counts,
 * and clean attack-graph metrics with interpretation notes.
 */

import { getCy } from '../graph/core';
import { fetchStats, getScans } from '../services/api';
import {
    computeMetrics,
    downloadMetricsCSV,
    downloadMetricsJSON,
    buildDataSourceSnapshot,
    findCrossings,
    getVisibleEdgeEndpoints,
    getVisibleNodePoints,
    computeBoundingBox,
    computeMeanEdgeLength,
    computeEdgeLengthStd,
    type DrawingMetrics,
    type DataSourceSnapshot,
} from '../features/metrics';
import { gatherCurrentSettings, type SettingsSnapshot } from '../features/settingsSnapshot';

// Most recently computed metrics — used by Export CSV button
let lastMetrics: DrawingMetrics | null = null;

// Sum of Trivy-reported vulnerabilities across all uploaded scans. Populated
// when the Statistics modal opens; included in CSV export.
let lastTrivyVulnCount: number | null = null;

// Settings + data-source snapshots taken at the moment metrics were computed.
// Used by the JSON export to ensure the downloaded file's settings match its
// metrics (Risk #5 in JSON_Export_With_Settings.md).
let lastSettings: SettingsSnapshot | null = null;
let lastDataSource: DataSourceSnapshot | null = null;

// Tracks IDs of every debug element we add so we can clean them up.
let debugElementIds: string[] = [];

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
    await populateTrivyVulnCount();
    populateCleanMetrics();
    populateDrawingMetrics();
    await captureSettingsSnapshot();
    wireExportButton();
}

/**
 * Fetch the sum of Trivy-reported per-package vulnerability entries across
 * all uploaded scans. This is the raw Trivy count (e.g. the "189 vulns" label
 * in the data source panel) — distinct from the unique CVE count derived
 * from the live graph. Persisted in lastTrivyVulnCount for CSV export.
 */
async function populateTrivyVulnCount(): Promise<void> {
    try {
        const { scans } = await getScans();
        lastTrivyVulnCount = scans.reduce((sum, s) => sum + (s.vuln_count || 0), 0);
        // Capture data-source snapshot from the same scan list — keeps the
        // JSON export's data_source consistent with the displayed Trivy count.
        lastDataSource = buildDataSourceSnapshot(scans);
    } catch (err) {
        console.error('Failed to fetch scan list for Trivy vuln count:', err);
        lastTrivyVulnCount = null;
        lastDataSource = null;
    }
}

/**
 * Capture a settings snapshot at the moment of metrics computation. Async
 * because /api/config is fetched once per call. Failures fall back to a
 * sensible default snapshot rather than disabling the JSON export, since
 * the metrics themselves are still valid.
 */
async function captureSettingsSnapshot(): Promise<void> {
    try {
        lastSettings = await gatherCurrentSettings();
    } catch (err) {
        console.error('Failed to gather settings snapshot:', err);
        lastSettings = null;
    }
}

/**
 * Populate live stats from the current Cytoscape graph.
 */
function populateLiveStats(): void {
    const cy = getCy();
    if (!cy) return;

    const isDebugNode = (type: string) =>
        type === 'CROSSING_DEBUG' || type === 'AREA_DEBUG' || type === 'UNIT_EDGE_NODE';

    const visibleNodes = cy.nodes().filter(n =>
        !n.hasClass('exploit-hidden') && !isDebugNode(n.data('type'))
    );
    const visibleEdges = cy.edges().filter(e => {
        if (e.hasClass('exploit-hidden')) return false;
        const t = e.data('type');
        return t !== 'UNIT_EDGE' && t !== 'UNIT_EDGE_STD';
    });

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

/**
 * Compute and display drawing quality metrics (Purchase 2002).
 */
function populateDrawingMetrics(): void {
    lastMetrics = computeMetrics();
    const tableBody = document.querySelector('#stats-drawing-table tbody');
    if (!tableBody) return;
    tableBody.innerHTML = '';

    if (!lastMetrics) {
        tableBody.innerHTML = '<tr><td colspan="2">No graph loaded</td></tr>';
        return;
    }

    const m = lastMetrics;
    const trivyLabel = lastTrivyVulnCount !== null
        ? `${lastTrivyVulnCount}   (all uploaded scans)`
        : '—';
    const rows: Array<[string, string]> = [
        ['Unique CVEs (graph)', String(m.uniqueCves)],
        ['Trivy vulnerabilities (scans)', trivyLabel],
        ['Edge crossings (raw)', String(m.crossingsRaw)],
        ['Edge crossings (normalized, Purchase)', m.crossingsNormalized.toFixed(4) + '   (1 = no crossings)'],
        ['Edge crossings per edge', m.crossingsPerEdge.toFixed(4) + '   (lower = cleaner)'],
        ['Drawing area (logical units²)', m.drawingArea.toFixed(2)],
        ['Area per node (logical units²)', m.areaPerNode.toFixed(2) + '   (lower = denser)'],
        ['Edge length CV', m.edgeLengthCV.toFixed(4) + '   (0 = uniform)']
    ];

    rows.forEach(([label, value]) => {
        const tr = document.createElement('tr');
        const td1 = document.createElement('td');
        td1.textContent = label;
        const td2 = document.createElement('td');
        td2.textContent = value;
        tr.appendChild(td1);
        tr.appendChild(td2);
        tableBody.appendChild(tr);
    });
}

/**
 * Wire the Export CSV button to download the most recently computed metrics.
 */
function wireExportButton(): void {
    const csvBtn = document.getElementById('stats-export-csv') as HTMLButtonElement | null;
    if (csvBtn) {
        csvBtn.disabled = !lastMetrics;
        // Replace handler (avoids stacking listeners on repeated opens)
        csvBtn.onclick = () => {
            if (lastMetrics) {
                downloadMetricsCSV(lastMetrics, {
                    trivyVulnCount: lastTrivyVulnCount ?? undefined,
                });
            }
        };
    }

    const jsonBtn = document.getElementById('stats-export-json') as HTMLButtonElement | null;
    if (jsonBtn) {
        // JSON export needs the settings + data-source snapshots in addition to
        // the metrics themselves; require all three before enabling.
        jsonBtn.disabled = !lastMetrics || !lastSettings || !lastDataSource;
        jsonBtn.onclick = () => {
            if (lastMetrics && lastSettings && lastDataSource) {
                downloadMetricsJSON(
                    lastMetrics,
                    { trivyVulnCount: lastTrivyVulnCount ?? undefined },
                    lastSettings,
                    lastDataSource,
                );
            }
        };
    }

    wireCrossingsToggle();
}

/**
 * Wire the "Show debug overlay" toggle: overlays crossings (red dots),
 * drawing-area bounding box (blue dashed rectangle), and a unit edge
 * (green line showing mean edge length).
 */
function wireCrossingsToggle(): void {
    const btn = document.getElementById('stats-toggle-crossings') as HTMLButtonElement | null;
    if (!btn) return;

    updateCrossingsToggleLabel(btn);

    btn.onclick = () => {
        if (debugElementIds.length > 0) {
            clearDebugOverlay();
        } else {
            drawDebugOverlay();
        }
        updateCrossingsToggleLabel(btn);
    };
}

function updateCrossingsToggleLabel(btn: HTMLButtonElement): void {
    if (debugElementIds.length > 0) {
        btn.textContent = `❌ Hide debug overlay`;
    } else {
        btn.textContent = '🔍 Show debug overlay';
    }
}

/**
 * Draw all three debug overlays:
 *   1. Red dots at each counted edge crossing
 *   2. Blue dashed rectangle around the bounding box, labeled with W×H
 *   3. Green line outside the graph with length = mean edge length
 */
function drawDebugOverlay(): void {
    const cy = getCy();
    if (!cy) return;

    clearDebugOverlay();

    // --- 1. Crossing dots ---
    const edges = getVisibleEdgeEndpoints();
    const crossings = findCrossings(edges);

    crossings.forEach((c, idx) => {
        const id = `__crossing_debug_${idx}`;
        cy.add({
            group: 'nodes',
            data: {
                id,
                type: 'CROSSING_DEBUG',
                edgeA: `${c.edgeA.sourceId} → ${c.edgeA.targetId}`,
                edgeB: `${c.edgeB.sourceId} → ${c.edgeB.targetId}`
            },
            position: { x: c.point.x, y: c.point.y },
            selectable: false,
            grabbable: false
        });
        debugElementIds.push(id);
    });

    // --- 2. Drawing-area bounding box ---
    const points = getVisibleNodePoints();
    const bb = computeBoundingBox(points);
    if (bb) {
        const w = bb.maxX - bb.minX;
        const h = bb.maxY - bb.minY;
        if (w > 0 && h > 0) {
            const cx = (bb.minX + bb.maxX) / 2;
            const cy2 = (bb.minY + bb.maxY) / 2;
            const id = '__area_debug';
            cy.add({
                group: 'nodes',
                data: {
                    id,
                    type: 'AREA_DEBUG',
                    label: `Drawing area  ${w.toFixed(0)} × ${h.toFixed(0)}`
                },
                position: { x: cx, y: cy2 },
                style: {
                    width: w,
                    height: h
                },
                selectable: false,
                grabbable: false
            });
            debugElementIds.push(id);
        }
    }

    // --- 3. Unit edges: mean length + std-dev length ---
    const meanLen = computeMeanEdgeLength(edges);
    const stdLen = computeEdgeLengthStd(edges);
    if (bb && meanLen > 0) {
        const yPad = Math.max(30, (bb.maxY - bb.minY) * 0.04);
        const yMean = bb.minY - yPad;
        const yStd = yMean - Math.max(20, (bb.maxY - bb.minY) * 0.025);

        addUnitEdge(cy, '__unit_mean', bb.minX, yMean, meanLen,
            `mean edge length: ${meanLen.toFixed(1)}`, 'UNIT_EDGE');

        if (stdLen > 0) {
            addUnitEdge(cy, '__unit_std', bb.minX, yStd, stdLen,
                `std dev: ${stdLen.toFixed(1)}`, 'UNIT_EDGE_STD');
        }
    }
}

/**
 * Helper: add a horizontal reference edge of a given length at (x, y)
 * going right. Tracks created element IDs in debugElementIds.
 */
function addUnitEdge(
    cy: any,
    idPrefix: string,
    x: number,
    y: number,
    length: number,
    label: string,
    edgeType: string
): void {
    const startId = `${idPrefix}_start`;
    const endId = `${idPrefix}_end`;
    const edgeId = `${idPrefix}_line`;

    cy.add({
        group: 'nodes',
        data: { id: startId, type: 'UNIT_EDGE_NODE' },
        position: { x, y },
        selectable: false,
        grabbable: false
    });
    cy.add({
        group: 'nodes',
        data: { id: endId, type: 'UNIT_EDGE_NODE' },
        position: { x: x + length, y },
        selectable: false,
        grabbable: false
    });
    cy.add({
        group: 'edges',
        data: {
            id: edgeId,
            source: startId,
            target: endId,
            type: edgeType,
            label
        }
    });
    debugElementIds.push(startId, endId, edgeId);
}

/**
 * Remove all debug overlay elements from the graph.
 */
function clearDebugOverlay(): void {
    const cy = getCy();
    if (!cy) {
        debugElementIds = [];
        return;
    }
    debugElementIds.forEach(id => {
        const el = cy.getElementById(id);
        if (el.length) el.remove();
    });
    debugElementIds = [];
}

// Expose globals for onclick handlers in index.html
(window as any).openStatistics = openStatistics;
(window as any).closeStatistics = closeStatistics;
