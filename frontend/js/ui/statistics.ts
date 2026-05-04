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
    type DrawingMetrics,
    type DataSourceSnapshot,
} from '../features/metrics';
import { gatherCurrentSettings, type SettingsSnapshot } from '../features/settingsSnapshot';
import { getSelectedScanIds } from '../features/dataSource';
import {
    showDebugOverlay,
    hideDebugOverlay,
    isDebugOverlayActive,
    countEnabledOverlays,
    getOverlayState,
    openDebugOverlayModal,
    syncStressVisualizationState,
} from './debugOverlay';

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
    // Re-bind the M1 stress-vis tap listener on the current cy.
    // Modal-open is the most reliable rebind point: cy exists by now
    // (a Statistics modal without a graph is meaningless), and a graph
    // rebuild between modal opens would have left the prior listener
    // orphaned on a destroyed cy instance. No-op if both stress modes
    // are off.
    syncStressVisualizationState();
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
        // Filter the displayed Trivy total to the user's scan-selector choice
        // — when one scan is selected, only that scan's vuln_count contributes.
        // The JSON export's data_source uses the same selection so the file
        // and the modal agree.
        const selectedIds = getSelectedScanIds();
        const selectedSet = selectedIds && selectedIds.length > 0 ? new Set(selectedIds) : null;
        const contributing = selectedSet ? scans.filter(s => selectedSet.has(s.id)) : scans;
        lastTrivyVulnCount = contributing.reduce((sum, s) => sum + (s.vuln_count || 0), 0);
        lastDataSource = buildDataSourceSnapshot(scans, selectedIds);
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

/**
 * Render the M21 compound-size distribution as a compact `size:count`
 * histogram string for the modal table. Sorted by size ascending.
 *
 * Example: `{2: 5, 3: 8, 4: 2}` → `"2×5  3×8  4×2"` (12 px-wide, scannable).
 */
function formatSizeDistribution(dist: Record<number, number>): string {
    const entries = Object.entries(dist)
        .map(([size, count]) => [Number(size), count] as const)
        .sort((a, b) => a[0] - b[0]);
    if (entries.length === 0) return '—';
    return entries.map(([size, count]) => `${size}×${count}`).join('  ');
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
    const scansContributing = lastDataSource?.scans_in_current_graph.length ?? 0;
    const totalUploaded = lastDataSource?.scans_uploaded_total ?? 0;
    const scansLabel = lastDataSource?.selection_was_implicit
        ? `all ${totalUploaded} uploaded scan${totalUploaded === 1 ? '' : 's'}`
        : `${scansContributing} of ${totalUploaded} uploaded scan${totalUploaded === 1 ? '' : 's'}`;
    const trivyLabel = lastTrivyVulnCount !== null
        ? `${lastTrivyVulnCount}   (${scansLabel})`
        : '—';
    const noCrossings = m.crossingsRaw === 0;
    const rows: Array<[string, string]> = [
        ['Unique CVEs (graph)', String(m.uniqueCves)],
        ['Trivy vulnerabilities (scans)', trivyLabel],
        ['Edge crossings (raw)', String(m.crossingsRaw)],
        ['Edge crossings (normalized, Purchase)', m.crossingsNormalized.toFixed(4) + '   (1 = no crossings)'],
        ['Edge crossings per edge', m.crossingsPerEdge.toFixed(4) + '   (lower = cleaner)'],
        [
            'Mean crossing angle (M2)',
            noCrossings ? '—' : m.crossingsMeanAngleDeg.toFixed(1) + '°   (90° = ideal)',
        ],
        [
            'Minimum crossing angle (M2)',
            noCrossings ? '—' : m.crossingsMinAngleDeg.toFixed(1) + '°   (worst case)',
        ],
        [
            'Right-angle ratio (M2)',
            noCrossings ? '—' : m.crossingsRightAngleRatio.toFixed(4) + '   (within ±15° of 90°)',
        ],
        [
            'Top crossing type pair (M25)',
            noCrossings
                ? '—'
                : `${m.crossingsTopPairLabel}   (${(m.crossingsTopPairShare * 100).toFixed(1)}%)`,
        ],
        [
            'Stress per pair (M1)',
            m.stressReachablePairs > 0
                ? `${m.stressPerPair.toFixed(2)}   (${m.stressReachablePairs} pairs${m.stressUnreachablePairs > 0 ? `, ${m.stressUnreachablePairs} unreachable` : ''})`
                : '—',
        ],
        [
            'Stress / mean edge length (M1)',
            m.stressReachablePairs > 0
                ? `${m.stressPerPairNormalizedEdge.toFixed(4)}   (Kamada-Kawai, dimensionless)`
                : '—',
        ],
        [
            'Stress / bbox diagonal (M1)',
            m.stressReachablePairs > 0
                ? `${m.stressPerPairNormalizedDiagonal.toFixed(4)}   (dimensionless)`
                : '—',
        ],
        [
            'Stress / √area (M1)',
            m.stressReachablePairs > 0
                ? `${m.stressPerPairNormalizedArea.toFixed(4)}   (dimensionless)`
                : '—',
        ],
        ['Drawing area (logical units²)', m.drawingArea.toFixed(2)],
        ['Area per node (logical units²)', m.areaPerNode.toFixed(2) + '   (lower = denser)'],
        ['Aspect ratio (M9)', m.aspectRatio.toFixed(4) + '   (1 = square)'],
        ['Edge length CV', m.edgeLengthCV.toFixed(4) + '   (0 = uniform)'],
        ['Compound groups (M21)', String(m.compoundGroupsCount)],
        ['Largest compound group (M21)', String(m.compoundLargestGroupSize)],
        ['Compound singleton fraction (M21)', m.compoundSingletonFraction.toFixed(4)],
        [
            'Compound size distribution (M21)',
            formatSizeDistribution(m.compoundSizeDistribution),
        ],
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

    wireDebugOverlayToggle();
}

/**
 * Wire the "🔍 Show debug overlay" button to the new debugOverlay module.
 *
 * Single click toggles overlays on/off using the user's last-saved
 * `OverlayState` (default on first use: the 4 existing overlays). The
 * `⚙️ Debug overlay settings` button next to it opens the new modal where
 * each overlay can be toggled individually.
 */
function wireDebugOverlayToggle(): void {
    const toggleBtn = document.getElementById('stats-toggle-crossings') as HTMLButtonElement | null;
    if (toggleBtn) {
        updateOverlayToggleLabel(toggleBtn);
        toggleBtn.onclick = () => {
            if (isDebugOverlayActive()) {
                hideDebugOverlay();
            } else {
                showDebugOverlay();
            }
            updateOverlayToggleLabel(toggleBtn);
        };
    }

    const settingsBtn = document.getElementById('stats-debug-overlay-settings') as HTMLButtonElement | null;
    if (settingsBtn) {
        settingsBtn.onclick = () => openDebugOverlayModal();
    }
}

/**
 * Reflect the active overlay state in the toggle button label so the user
 * knows whether clicking will turn overlays on or off, and how many will
 * appear when on.
 */
function updateOverlayToggleLabel(btn: HTMLButtonElement): void {
    if (isDebugOverlayActive()) {
        btn.textContent = '❌ Hide debug overlay';
    } else {
        const n = countEnabledOverlays(getOverlayState());
        btn.textContent = n === 0
            ? '🔍 Show debug overlay (none active)'
            : `🔍 Show debug overlay (${n})`;
    }
}

// Expose globals for onclick handlers in index.html
(window as any).openStatistics = openStatistics;
(window as any).closeStatistics = closeStatistics;
