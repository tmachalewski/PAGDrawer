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
    // The Drawing Quality Metrics section is split across two tables to
    // balance the modal layout — left for paper-headline aesthetic
    // metrics (Counts / Crossings / Stress), right for geometry +
    // reduction-evaluating groups.
    const leftBody = document.querySelector('#stats-drawing-table-left tbody');
    const rightBody = document.querySelector('#stats-drawing-table-right tbody');
    if (!leftBody || !rightBody) return;
    leftBody.innerHTML = '';
    rightBody.innerHTML = '';

    if (!lastMetrics) {
        rightBody.innerHTML = '<tr><td colspan="2">No graph loaded</td></tr>';
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
    const noStress = m.stressReachablePairs === 0;

    // Grouped row structure. A "group" header gives the visual separator;
    // each "row" is the same [label, value] pair as before. Order within
    // groups is deliberate — the most-cited / paper-headline metric in
    // each section comes first.
    type Row = { kind: 'group'; label: string } | { kind: 'row'; label: string; value: string };
    const leftRows: Row[] = [
        { kind: 'group', label: 'Counts' },
        { kind: 'row', label: 'Unique CVEs (graph)', value: String(m.uniqueCves) },
        { kind: 'row', label: 'Trivy vulnerabilities (scans)', value: trivyLabel },

        { kind: 'group', label: 'Edge crossings (M2 + M25)' },
        { kind: 'row', label: 'Edge crossings (raw)', value: String(m.crossingsRaw) },
        { kind: 'row', label: 'Edge crossings (normalized, Purchase)', value: m.crossingsNormalized.toFixed(4) + '   (1 = no crossings)' },
        { kind: 'row', label: 'Edge crossings per edge', value: m.crossingsPerEdge.toFixed(4) + '   (lower = cleaner)' },
        { kind: 'row', label: 'Mean crossing angle (M2)', value: noCrossings ? '—' : m.crossingsMeanAngleDeg.toFixed(1) + '°   (90° = ideal)' },
        { kind: 'row', label: 'Minimum crossing angle (M2)', value: noCrossings ? '—' : m.crossingsMinAngleDeg.toFixed(1) + '°   (worst case)' },
        { kind: 'row', label: 'Right-angle ratio (M2)', value: noCrossings ? '—' : m.crossingsRightAngleRatio.toFixed(4) + '   (within ±15° of 90°)' },
        { kind: 'row', label: 'Top crossing type pair (M25)', value: noCrossings ? '—' : `${m.crossingsTopPairLabel}   (${(m.crossingsTopPairShare * 100).toFixed(1)}%)` },

        { kind: 'group', label: 'Layout fidelity — Stress (M1)' },
        { kind: 'row', label: 'Stress per pair (raw)', value: noStress ? '—' : `${m.stressPerPair.toFixed(2)}   (${m.stressReachablePairs} pairs${m.stressUnreachablePairs > 0 ? `, ${m.stressUnreachablePairs} unreachable` : ''})` },
        { kind: 'row', label: 'Stress / mean edge length', value: noStress ? '—' : `${m.stressPerPairNormalizedEdge.toFixed(4)}   (Kamada-Kawai, dimensionless)` },
        { kind: 'row', label: 'Stress / bbox diagonal', value: noStress ? '—' : `${m.stressPerPairNormalizedDiagonal.toFixed(4)}   (dimensionless)` },
        { kind: 'row', label: 'Stress / √area', value: noStress ? '—' : `${m.stressPerPairNormalizedArea.toFixed(4)}   (dimensionless)` },
    ];

    const rightRows: Row[] = [
        { kind: 'group', label: 'Layout geometry' },
        { kind: 'row', label: 'Drawing area (logical units²)', value: m.drawingArea.toFixed(2) },
        { kind: 'row', label: 'Bounding box (W × H)', value: `${m.bboxWidth.toFixed(2)} × ${m.bboxHeight.toFixed(2)}` },
        { kind: 'row', label: 'Area per node (logical units²)', value: m.areaPerNode.toFixed(2) + '   (lower = denser)' },
        { kind: 'row', label: 'Aspect ratio (M9)', value: m.aspectRatio.toFixed(4) + '   (1 = square)' },
        { kind: 'row', label: 'Edge length CV', value: m.edgeLengthCV.toFixed(4) + '   (0 = uniform)' },
        { kind: 'row', label: 'Edge length mean / std', value: m.edgeLengthMean > 0 ? `${m.edgeLengthMean.toFixed(2)}  /  ${m.edgeLengthStd.toFixed(2)}   (CV = ${(m.edgeLengthStd / m.edgeLengthMean).toFixed(4)})` : '—' },

        { kind: 'group', label: 'Reductions: bridges + merges (M19 + M20 + M21)' },
        { kind: 'row', label: 'Bridge edge proportion (M19)', value: m.bridgeEdgeCount === 0 ? '—   (no visibility-toggle bridges)' : `${m.bridgeEdgeProportion.toFixed(4)}   (${m.bridgeEdgeCount} bridges)` },
        { kind: 'row', label: 'Mean contraction depth (M19)', value: m.bridgeEdgeCount === 0 ? '—' : `${m.meanContractionDepth.toFixed(2)}   (hidden hops per bridge)` },
        { kind: 'row', label: 'Bridge chain-length distribution (M19)', value: m.bridgeEdgeCount === 0 ? '—' : formatSizeDistribution(m.bridgeChainLengthDistribution) },
        { kind: 'row', label: 'Edge consolidation ratio (M20, weighted)', value: m.ecrCompoundsCount === 0 ? '—   (no synthetic-edge compounds)' : `${m.meanEcrWeighted.toFixed(2)}×   (over ${m.ecrCompoundsCount} compounds)` },
        { kind: 'row', label: 'Compound groups (M21)', value: String(m.compoundGroupsCount) },
        { kind: 'row', label: 'Largest compound group (M21)', value: String(m.compoundLargestGroupSize) },
        { kind: 'row', label: 'Compound singleton fraction (M21)', value: m.compoundSingletonFraction.toFixed(4) },
        { kind: 'row', label: 'Compound size distribution (M21)', value: formatSizeDistribution(m.compoundSizeDistribution) },

        { kind: 'group', label: 'Reduction potential (M22)' },
        { kind: 'row', label: 'Attribute compression ratio (M22)', value: m.acrCveNodeCount === 0 ? '—   (no visible CVEs)' : `prereqs ${m.acrCvePrereqs.toFixed(4)}  /  outcomes ${m.acrCveOutcomes.toFixed(4)}   (${m.acrCveNodeCount} CVEs)` },
    ];

    const renderInto = (body: Element, items: Row[]) => {
        items.forEach(item => {
            if (item.kind === 'group') {
                const tr = document.createElement('tr');
                tr.className = 'stats-group-header';
                const td = document.createElement('td');
                td.colSpan = 2;
                td.textContent = item.label;
                tr.appendChild(td);
                body.appendChild(tr);
                return;
            }
            const tr = document.createElement('tr');
            const td1 = document.createElement('td');
            td1.textContent = item.label;
            const td2 = document.createElement('td');
            td2.textContent = item.value;
            tr.appendChild(td1);
            tr.appendChild(td2);
            body.appendChild(tr);
        });
    };
    renderInto(leftBody, leftRows);
    renderInto(rightBody, rightRows);
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
