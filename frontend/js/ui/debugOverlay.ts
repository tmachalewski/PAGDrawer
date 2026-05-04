/**
 * Debug overlay module — extracted from `statistics.ts` and generalised
 * around a per-overlay state machine with localStorage persistence and
 * named presets.
 *
 * Each overlay is independently toggleable via `OverlayState`. The four
 * existing overlays (red crossings dots, blue bbox, green mean-edge line,
 * orange std-dev line) carry their original behaviour; new toggles are:
 *
 *   - `aspectRatio`      — M9 — extends the bbox label with `(AR = 0.42)`
 *   - `groupCardinality` — M21 — appends `(×N)` to every compound-parent
 *                                 label so all compound types (CVE_GROUP,
 *                                 COMPOUND/Initial-State, ATTACKER_BOX
 *                                 child boxes, …) advertise their size
 *
 * State persists in `localStorage` under a versioned key so a future
 * schema change can reset cleanly.
 */

import { getCy } from '../graph/core';
import {
    findCrossings,
    getVisibleEdgeEndpoints,
    getVisibleNodePoints,
    getVisibleNodesWithIds,
    computeBoundingBox,
    computeMeanEdgeLength,
    computeEdgeLengthStd,
    computeAspectRatio,
    computeCompoundCardinality,
    computeAPSP,
    symmetrizedDistance,
    type CrossingInfo,
    type NodeWithPosition,
} from '../features/metrics';

// =============================================================================
// State machine
// =============================================================================

export type CrossingsColorMode = 'none' | 'angle' | 'typePair';

export interface OverlayState {
    crossings: boolean;        // existing — red dots at every counted crossing
    drawingArea: boolean;      // existing — blue dashed bbox rectangle
    meanEdgeLine: boolean;     // existing — green horizontal line, length = mean
    stdDevLine: boolean;       // existing — orange horizontal line, length = std
    aspectRatio: boolean;      // M9      — extends bbox label with "(AR = 0.42)"
    groupCardinality: boolean; // M21     — appends "(×N)" to compound-parent labels
    /**
     * Crossings dot colour scheme. M2 + M25 share the same dot, so we
     * disambiguate via a radio choice rather than independent toggles:
     *   - 'none'    : default red (#ff2d55), back-compat with v0
     *   - 'angle'   : M2  — red (acute) → yellow (45°) → green (≈90°)
     *   - 'typePair': M25 — categorical palette per (typeA × typeB) bucket
     */
    crossingsColorBy: CrossingsColorMode;
    /**
     * M1 visualisation — colour every reachable node by symmetrised graph
     * distance from the most-recently-clicked node. Red = close (distance 1),
     * green = far (max distance), grey = unreachable. The clicked node
     * itself is rendered with a yellow outline. See StressMetric.md.
     */
    stressDistanceColoring: boolean;
    /**
     * M1 visualisation — clicking two nodes in sequence pops a small
     * floating panel showing the directed distances in both directions,
     * the symmetrised distance, and the Euclidean (layout) distance.
     * Useful for explaining the metric or sanity-checking individual pairs.
     */
    stressPairDistance: boolean;
}

export const DEFAULT_OVERLAY_STATE: OverlayState = {
    crossings: true,
    drawingArea: true,
    meanEdgeLine: true,
    stdDevLine: true,
    aspectRatio: false,
    groupCardinality: false,
    crossingsColorBy: 'none',
    stressDistanceColoring: false,
    stressPairDistance: false,
};

const STORAGE_KEY = 'debugOverlayState_v1';

export type PresetName =
    | 'crossings'      // 🎯 Crossings analysis
    | 'layout'         // 📐 Layout diagnostics
    | 'reductions'     // 🔗 Reduction transparency
    | 'defaults'       // ◌  Defaults (existing 4 overlays only)
    | 'clear';         // ⊘  Clear all

export const PRESETS: Record<PresetName, OverlayState> = {
    crossings: {
        crossings: true,
        drawingArea: false,
        meanEdgeLine: false,
        stdDevLine: false,
        aspectRatio: true,
        groupCardinality: false,
        crossingsColorBy: 'typePair',  // M25 — per the Debug-Overlay plan
        stressDistanceColoring: false,
        stressPairDistance: false,
    },
    layout: {
        crossings: false,
        drawingArea: true,
        meanEdgeLine: true,
        stdDevLine: true,
        aspectRatio: true,
        groupCardinality: false,
        crossingsColorBy: 'none',
        stressDistanceColoring: false,
        stressPairDistance: false,
    },
    reductions: {
        crossings: false,
        drawingArea: false,
        meanEdgeLine: false,
        stdDevLine: false,
        aspectRatio: false,
        groupCardinality: true,
        crossingsColorBy: 'none',
        stressDistanceColoring: false,
        stressPairDistance: false,
    },
    defaults: { ...DEFAULT_OVERLAY_STATE },
    clear: {
        crossings: false,
        drawingArea: false,
        meanEdgeLine: false,
        stdDevLine: false,
        aspectRatio: false,
        groupCardinality: false,
        crossingsColorBy: 'none',
        stressDistanceColoring: false,
        stressPairDistance: false,
    },
};

// Module-private state. Loaded from localStorage on first import.
let currentState: OverlayState = loadState();

// Tracks whether the overlay is currently rendered on the canvas. Distinct
// from `currentState` (which says *which* overlays the user wants when active).
let isActive = false;

// IDs of every Cytoscape pseudo-element added by the overlay. Used for cleanup.
let elementIds: string[] = [];

// For M21: when we modify a compound parent's label we save the original here
// so `clearAll()` can restore exactly what the data layer had.
let originalParentLabels: Map<string, string> | null = null;

// =============================================================================
// Public API
// =============================================================================

export function getOverlayState(): OverlayState {
    return { ...currentState };
}

export function setOverlayState(partial: Partial<OverlayState>): void {
    const prev = currentState;
    currentState = { ...currentState, ...partial };
    persistState(currentState);

    // Clear stress-vis visuals when their respective mode is turned OFF.
    // We don't clear when other overlays toggle (preserving the user's
    // stress-vis context) or when these modes turn ON (no visuals exist
    // yet — they materialise on the next click).
    if (prev.stressDistanceColoring && !currentState.stressDistanceColoring) {
        clearDistanceColoring();
    }
    if (prev.stressPairDistance && !currentState.stressPairDistance) {
        hideStressPairPanel();
    }

    // Stress visualisations are click-driven, not render-driven — they
    // need their listener bound regardless of whether the rest of the
    // overlay (crossings dots, bbox, etc.) is currently shown.
    syncStressVisualizationState();
    if (isActive) redraw();
}

export function applyPreset(name: PresetName): void {
    setOverlayState(PRESETS[name]);
}

export function isDebugOverlayActive(): boolean {
    return isActive;
}

/**
 * Number of overlays currently enabled in `currentState`. Useful for the
 * Statistics-modal button label, e.g. `🔍 Debug overlays (3 active)`.
 *
 * Only counts the boolean toggles. The crossingsColorBy radio is a
 * sub-mode of the `crossings` toggle and not counted on its own.
 */
export function countEnabledOverlays(state: OverlayState = currentState): number {
    const flags: boolean[] = [
        state.crossings,
        state.drawingArea,
        state.meanEdgeLine,
        state.stdDevLine,
        state.aspectRatio,
        state.groupCardinality,
        state.stressDistanceColoring,
        state.stressPairDistance,
    ];
    return flags.filter(Boolean).length;
}

/**
 * Render every overlay enabled in `currentState`. Idempotent — calling twice
 * just clears and re-renders.
 */
export function showDebugOverlay(): void {
    if (isActive) clearAll();
    drawAll();
    isActive = true;
    // Make sure the stress vis listener is bound on the current cy
    // instance — a graph rebuild between toggles would otherwise leave
    // the listener orphaned on the old (destroyed) instance.
    syncStressVisualizationState();
}

/**
 * Remove every rendered overlay element + tear down stress vis state.
 * Restores any compound-parent labels we modified for M21.
 *
 * This is the full reset; `clearAll()` (used by `redraw()`) only tears
 * down synthetic overlay elements so toggling individual overlays
 * doesn't disturb the user's stress-vis context.
 */
export function hideDebugOverlay(): void {
    clearAll();
    unwireStressVisualizationHandlers();
    isActive = false;
}

// =============================================================================
// Drawing
// =============================================================================

function redraw(): void {
    clearAll();
    drawAll();
}

function drawAll(): void {
    const cy = getCy();
    if (!cy) return;

    const edges = getVisibleEdgeEndpoints();
    const points = getVisibleNodePoints();
    const bb = computeBoundingBox(points);

    // 1. Crossings dots — colored per `crossingsColorBy` (M2 angle / M25 type pair)
    if (currentState.crossings) {
        const crossings = findCrossings(edges);
        const typePairPalette = buildTypePairPalette(crossings);
        crossings.forEach((c, idx) => {
            const id = `__crossing_debug_${idx}`;
            const color = pickCrossingColor(c, currentState.crossingsColorBy, typePairPalette);
            const angleDeg = (c.angle * 180) / Math.PI;
            const typePair = `${c.edgeAType}×${c.edgeBType}`;
            // Pretty-print fields shown by the standard tooltip when the
            // user clicks (or hovers) the dot. The tooltip iterates every
            // string/number key in `data`, so naming + formatting these
            // fields is what shapes the user-facing layout.
            const angleField = `${angleDeg.toFixed(1)}°`;
            const pairField = typePair === '×' ? '—' : typePair;
            const added = cy.add({
                group: 'nodes',
                data: {
                    id,
                    type: 'CROSSING_DEBUG',
                    'crossing angle': angleField,
                    'edge type pair': pairField,
                    'edge A': `${c.edgeA.sourceId} → ${c.edgeA.targetId}`,
                    'edge B': `${c.edgeB.sourceId} → ${c.edgeB.targetId}`,
                },
                position: { x: c.point.x, y: c.point.y },
                selectable: false,
                grabbable: false,
            });
            // Apply colour override AFTER add so Cytoscape doesn't warn
            // about a style bypass at element creation.
            if (color) added.style('background-color', color);
            elementIds.push(id);
        });
    }

    // 2. Drawing area bbox — optional M9 aspect ratio appended to label.
    if (currentState.drawingArea && bb) {
        const w = bb.maxX - bb.minX;
        const h = bb.maxY - bb.minY;
        if (w > 0 && h > 0) {
            const cx = (bb.minX + bb.maxX) / 2;
            const cy2 = (bb.minY + bb.maxY) / 2;
            const id = '__area_debug';
            const baseLabel = `Drawing area  ${w.toFixed(0)} × ${h.toFixed(0)}`;
            const label = currentState.aspectRatio
                ? `${baseLabel}  (AR = ${computeAspectRatio(bb).toFixed(2)})`
                : baseLabel;
            cy.add({
                group: 'nodes',
                data: { id, type: 'AREA_DEBUG', label },
                position: { x: cx, y: cy2 },
                style: { width: w, height: h },
                selectable: false,
                grabbable: false,
            });
            elementIds.push(id);
        }
    } else if (!currentState.drawingArea && currentState.aspectRatio && bb) {
        // Edge case: the user wants to see the aspect ratio but disabled the
        // bbox. The plan says M9 lives on the bbox label, so we silently no-op
        // — the AR toggle has no rendering target without the bbox.
    }

    // 3 + 4. Mean and std-dev unit edges (positioned just above the bbox).
    if (bb && (currentState.meanEdgeLine || currentState.stdDevLine)) {
        const yPad = Math.max(30, (bb.maxY - bb.minY) * 0.04);
        const yMean = bb.minY - yPad;
        const yStd = yMean - Math.max(20, (bb.maxY - bb.minY) * 0.025);

        if (currentState.meanEdgeLine) {
            const meanLen = computeMeanEdgeLength(edges);
            if (meanLen > 0) {
                addUnitEdge(cy, '__unit_mean', bb.minX, yMean, meanLen,
                    `mean edge length: ${meanLen.toFixed(1)}`, 'UNIT_EDGE');
            }
        }

        if (currentState.stdDevLine) {
            const stdLen = computeEdgeLengthStd(edges);
            if (stdLen > 0) {
                addUnitEdge(cy, '__unit_std', bb.minX, yStd, stdLen,
                    `std dev: ${stdLen.toFixed(1)}`, 'UNIT_EDGE_STD');
            }
        }
    }

    // 5. M21 — compound-parent cardinality badges.
    if (currentState.groupCardinality) {
        applyGroupCardinalityBadges();
    }

    // M1 stress visualisations are bound separately (see
    // syncStressVisualizationState). They survive show/hide of the
    // rest of the overlay because they're click-driven, not render-driven.
}

/**
 * Bind/unbind the M1 stress visualisation listener based on whether either
 * mode is currently enabled. Idempotent. Exported so `statistics.ts` can
 * call it on every modal refresh — that's the most reliable hook because
 * cy is guaranteed to exist by then, even after a graph rebuild.
 *
 * Also called from `setOverlayState` (whenever a checkbox toggles), from
 * `showDebugOverlay` / `openDebugOverlayModal`, and on first module
 * import as a best-effort attempt to honour persisted localStorage state.
 */
export function syncStressVisualizationState(): void {
    if (currentState.stressDistanceColoring || currentState.stressPairDistance) {
        wireStressVisualizationHandlers();
    } else {
        unwireStressVisualizationHandlers();
    }
}

/**
 * 10-color palette for M25 type-pair coloring. Picked to be distinguishable
 * on both light and dark themes. If a graph has more than 10 distinct
 * type-pairs, later pairs cycle — that's acceptable since the modal also
 * surfaces the top pair as a number.
 */
const TYPE_PAIR_PALETTE: ReadonlyArray<string> = [
    '#ef4444', '#f59e0b', '#eab308', '#84cc16', '#22c55e',
    '#06b6d4', '#3b82f6', '#8b5cf6', '#ec4899', '#6b7280',
];

/**
 * Walk the crossings once to build a deterministic mapping from type-pair
 * key to palette colour. Pairs are sorted by frequency then label so the
 * "biggest contributor" gets the first palette slot — which is red, the
 * most attention-grabbing colour.
 */
export function buildTypePairPalette(crossings: CrossingInfo[]): Map<string, string> {
    const counts = new Map<string, number>();
    for (const c of crossings) {
        const key = `${c.edgeAType}×${c.edgeBType}`;
        counts.set(key, (counts.get(key) || 0) + 1);
    }
    const sorted = Array.from(counts.entries()).sort((a, b) => {
        if (b[1] !== a[1]) return b[1] - a[1];
        return a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0;
    });
    const palette = new Map<string, string>();
    sorted.forEach(([key], idx) => {
        palette.set(key, TYPE_PAIR_PALETTE[idx % TYPE_PAIR_PALETTE.length]);
    });
    return palette;
}

/**
 * M2 — interpolate from red (0°, acute) → yellow (45°) → green (90°) along
 * the HSL hue axis. Returns a CSS hsl(...) string.
 */
export function angleToColor(angleRad: number): string {
    // Clamp into [0, π/2] then map to hue [0°, 120°].
    const clamped = Math.max(0, Math.min(Math.PI / 2, angleRad));
    const hue = (clamped / (Math.PI / 2)) * 120;
    return `hsl(${hue.toFixed(1)}, 75%, 50%)`;
}

/**
 * Resolve the CSS colour for a single crossing dot per the active radio
 * mode. Returns `null` for the `'none'` mode so the call-site can keep
 * the stylesheet's default red.
 */
export function pickCrossingColor(
    c: CrossingInfo,
    mode: CrossingsColorMode,
    typePairPalette: Map<string, string>,
): string | null {
    if (mode === 'none') return null;
    if (mode === 'angle') return angleToColor(c.angle);
    if (mode === 'typePair') {
        const key = `${c.edgeAType}×${c.edgeBType}`;
        return typePairPalette.get(key) || TYPE_PAIR_PALETTE[0];
    }
    return null;
}

/**
 * Helper: add a horizontal reference edge of given length at (x, y) going
 * right. Pseudo-elements use Cytoscape `type` selectors defined in
 * `frontend/js/config/constants.ts` (UNIT_EDGE_NODE, UNIT_EDGE, UNIT_EDGE_STD).
 */
function addUnitEdge(
    cy: ReturnType<typeof getCy>,
    idPrefix: string,
    x: number,
    y: number,
    length: number,
    label: string,
    edgeType: 'UNIT_EDGE' | 'UNIT_EDGE_STD',
): void {
    if (!cy) return;
    const startId = `${idPrefix}_start`;
    const endId = `${idPrefix}_end`;
    const edgeId = `${idPrefix}_line`;

    cy.add({
        group: 'nodes',
        data: { id: startId, type: 'UNIT_EDGE_NODE' },
        position: { x, y },
        selectable: false,
        grabbable: false,
    });
    cy.add({
        group: 'nodes',
        data: { id: endId, type: 'UNIT_EDGE_NODE' },
        position: { x: x + length, y },
        selectable: false,
        grabbable: false,
    });
    cy.add({
        group: 'edges',
        data: { id: edgeId, source: startId, target: endId, type: edgeType, label },
    });
    elementIds.push(startId, endId, edgeId);
}

/**
 * M21 — append `(×N)` to every compound parent's label that has children.
 * Saves originals to `originalParentLabels` for restoration.
 *
 * Idempotent: if a label already ends with `(×<digits>)`, leave it alone.
 * This protects (a) parents whose backend label already includes the count
 * (e.g. CVE_GROUP) and (b) repeated calls to `redraw()`.
 */
function applyGroupCardinalityBadges(): void {
    const cy = getCy();
    if (!cy) return;

    const card = computeCompoundCardinality();
    originalParentLabels = new Map();

    for (const g of card.groups) {
        const parent = cy.getElementById(g.parentId);
        if (parent.length === 0) continue;
        const original = String(parent.data('label') ?? '');
        originalParentLabels.set(g.parentId, original);

        if (/\(×\d+\)\s*$/.test(original)) continue;

        const newLabel = original.length > 0
            ? `${original}  (×${g.size})`
            : `(×${g.size})`;
        parent.data('label', newLabel);
    }
}

function clearGroupCardinalityBadges(): void {
    if (!originalParentLabels) return;
    const cy = getCy();
    if (!cy) {
        originalParentLabels = null;
        return;
    }
    for (const [parentId, original] of originalParentLabels) {
        const parent = cy.getElementById(parentId);
        if (parent.length === 0) continue;
        parent.data('label', original);
    }
    originalParentLabels = null;
}

// =============================================================================
// M1 stress visualisation — distance-from-source colouring + pair panel
// =============================================================================

/** Set of node ids currently overridden by the distance-coloring overlay. */
const stressColoredIds = new Set<string>();

/** First node clicked in pair-distance mode; null when no pair in progress. */
let stressPairFirst: string | null = null;

/**
 * Pure helper: given a clicked source id, the visible-node list, and a
 * directed APSP map, return the inline styles to apply to each node.
 *
 * Output is a Map<nodeId, partial-style-object>. The Cytoscape-side
 * applier just iterates and calls `node.style(...)`. Tests verify the
 * mapping without needing a real cy graph.
 *
 * Color scheme:
 *   - source              : black fill + yellow border (clearly stands out)
 *   - reachable, distance d (1 ≤ d ≤ maxDist):
 *                           hsl(120·d/maxDist, 75%, 55%) — red→yellow→green
 *   - unreachable          : translucent grey, no border change
 */
export function computeDistanceColoringStyles(
    sourceId: string,
    nodes: NodeWithPosition[],
    apsp: Map<string, Map<string, number>>,
): Map<string, Record<string, string | number>> {
    const result = new Map<string, Record<string, string | number>>();

    // Find the maximum reachable symmetrised distance (excluding source).
    let maxDist = 0;
    for (const n of nodes) {
        if (n.id === sourceId) continue;
        const d = symmetrizedDistance(apsp, sourceId, n.id);
        if (d !== undefined && d > maxDist) maxDist = d;
    }

    for (const n of nodes) {
        if (n.id === sourceId) {
            result.set(n.id, {
                'background-color': '#000000',
                'border-color': '#ffeb3b',
                'border-width': 4,
            });
            continue;
        }
        const d = symmetrizedDistance(apsp, sourceId, n.id);
        if (d === undefined) {
            result.set(n.id, { 'background-color': 'rgba(128, 128, 128, 0.4)' });
        } else {
            const t = maxDist > 0 ? d / maxDist : 0;
            const hue = (t * 120).toFixed(0); // 0=red, 120=green
            result.set(n.id, { 'background-color': `hsl(${hue}, 75%, 55%)` });
        }
    }
    return result;
}

/**
 * Apply distance-from-source coloring to every visible non-debug node.
 * Called on every click in stress-coloring mode. Idempotent — clears
 * any previous coloring before applying the new one.
 */
function applyDistanceColoring(sourceId: string): void {
    clearDistanceColoring();
    const cy = getCy();
    if (!cy) return;

    const nodes = getVisibleNodesWithIds();
    if (nodes.length === 0) return;
    const edges = getVisibleEdgeEndpoints();
    const apsp = computeAPSP(nodes.map(n => n.id), edges);

    const styles = computeDistanceColoringStyles(sourceId, nodes, apsp);
    styles.forEach((style, id) => {
        const node = cy.getElementById(id);
        if (node.length === 0) return;
        node.style(style);
        stressColoredIds.add(id);
    });
}

/**
 * Remove inline colour overrides from every node we touched, restoring
 * the stylesheet's default appearance.
 */
function clearDistanceColoring(): void {
    const cy = getCy();
    if (!cy) {
        stressColoredIds.clear();
        return;
    }
    const STYLE_KEYS = ['background-color', 'border-color', 'border-width'];
    stressColoredIds.forEach(id => {
        const node = cy.getElementById(id);
        if (node.length === 0) return;
        STYLE_KEYS.forEach(k => node.removeStyle(k));
    });
    stressColoredIds.clear();
}

/**
 * Pure helper: compute the four numbers shown in the pair-distance panel
 * given the two ids, their positions, and a directed APSP.
 *
 * Returns the displayable strings so the panel doesn't need to format
 * unreachable / number cases itself.
 */
export function computeStressPairDisplay(
    firstId: string,
    secondId: string,
    nodes: NodeWithPosition[],
    apsp: Map<string, Map<string, number>>,
): {
    forwardDistance: string;
    backwardDistance: string;
    symmetrizedDistance: string;
    euclideanDistance: string;
} {
    const dab = apsp.get(firstId)?.get(secondId);
    const dba = apsp.get(secondId)?.get(firstId);
    const sym = symmetrizedDistance(apsp, firstId, secondId);
    const a = nodes.find(n => n.id === firstId);
    const b = nodes.find(n => n.id === secondId);
    let euc = '—';
    if (a && b) {
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        euc = Math.sqrt(dx * dx + dy * dy).toFixed(1);
    }
    const fmt = (d: number | undefined) => d === undefined ? 'unreachable' : String(d);
    return {
        forwardDistance: fmt(dab),
        backwardDistance: fmt(dba),
        symmetrizedDistance: fmt(sym),
        euclideanDistance: euc,
    };
}

/**
 * Show the floating pair-distance panel with the four numbers for the
 * given pair. Called when the user clicks the second node in pair mode.
 */
function showStressPairPanel(firstId: string, secondId: string): void {
    const cy = getCy();
    if (!cy) return;
    const nodes = getVisibleNodesWithIds();
    const edges = getVisibleEdgeEndpoints();
    const apsp = computeAPSP(nodes.map(n => n.id), edges);
    const display = computeStressPairDisplay(firstId, secondId, nodes, apsp);

    setPanelText('stress-pair-from', firstId);
    setPanelText('stress-pair-to', secondId);
    setPanelText('stress-pair-fwd', display.forwardDistance);
    setPanelText('stress-pair-bwd', display.backwardDistance);
    setPanelText('stress-pair-sym', display.symmetrizedDistance);
    setPanelText('stress-pair-euc', display.euclideanDistance);

    const panel = document.getElementById('stress-pair-panel');
    if (panel) panel.style.display = 'block';
}

function setPanelText(id: string, value: string): void {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function hideStressPairPanel(): void {
    const panel = document.getElementById('stress-pair-panel');
    if (panel) panel.style.display = 'none';
    stressPairFirst = null;
}

/**
 * Bind a delegated tap listener on cy that drives both stress
 * visualisations. Idempotent — the namespaced handle is replaced on
 * each call. Synthetic debug nodes are filtered at fire-time.
 */
// Hold a direct reference to the bound handler so we can remove it
// reliably with `cy.off(event, handler)` — which is more deterministic
// than namespaced removal in some Cytoscape versions.
type CyTapHandler = (e: { target: unknown; cy?: unknown }) => void;
let stressVisHandler: CyTapHandler | null = null;
let stressVisBoundCy: unknown = null;

function wireStressVisualizationHandlers(): void {
    const cy = getCy();
    if (!cy) return;

    // Detach previous handler if any. If the cy changed (rebuild), the
    // old reference belongs to a destroyed cy and can't be safely
    // operated on, so we just drop it.
    if (stressVisHandler && stressVisBoundCy === cy) {
        (cy as { off: (event: string, h: CyTapHandler) => void }).off('tap', stressVisHandler);
    }
    stressVisHandler = null;
    stressVisBoundCy = null;

    // Build the new handler.
    const handler: CyTapHandler = (e) => {
        const target = e.target as {
            isNode?: () => boolean;
            data?: (k: string) => unknown;
            id?: () => string;
        };
        if (target === cy) {
            if (currentState.stressDistanceColoring) clearDistanceColoring();
            if (currentState.stressPairDistance) hideStressPairPanel();
            return;
        }
        if (typeof target?.isNode !== 'function' || !target.isNode()) return;
        const t = target.data?.('type');
        if (t === 'CROSSING_DEBUG' || t === 'AREA_DEBUG' || t === 'UNIT_EDGE_NODE') return;
        const id = target.id?.();
        if (typeof id !== 'string') return;

        if (currentState.stressDistanceColoring) {
            applyDistanceColoring(id);
        }
        if (currentState.stressPairDistance) {
            if (stressPairFirst === null) {
                stressPairFirst = id;
            } else if (stressPairFirst !== id) {
                showStressPairPanel(stressPairFirst, id);
                stressPairFirst = null;
            }
        }
    };

    (cy as { on: (event: string, h: CyTapHandler) => void }).on('tap', handler);
    stressVisHandler = handler;
    stressVisBoundCy = cy;
}

function unwireStressVisualizationHandlers(): void {
    const cy = getCy();
    if (cy && stressVisHandler && stressVisBoundCy === cy) {
        (cy as { off: (event: string, h: CyTapHandler) => void }).off('tap', stressVisHandler);
    }
    stressVisHandler = null;
    stressVisBoundCy = null;
    clearDistanceColoring();
    hideStressPairPanel();
}

/**
 * Tear down the synthetic overlay elements (crossing dots, bbox, unit
 * edges) and restore the labels we modified for M21. Called from
 * `redraw()` and `hideDebugOverlay()`.
 *
 * Does NOT touch the M1 stress visualisation state — those colours and
 * the pair-selection persist across overlay redraws so the user can
 * toggle other overlays (crossings, bbox, etc.) without losing their
 * stress-vis context. `hideDebugOverlay()` calls
 * `unwireStressVisualizationHandlers()` separately for the full reset.
 */
function clearAll(): void {
    const cy = getCy();
    if (cy) {
        elementIds.forEach(id => {
            const el = cy.getElementById(id);
            if (el.length) el.remove();
        });
    }
    elementIds = [];
    clearGroupCardinalityBadges();
}

// =============================================================================
// localStorage persistence
// =============================================================================

function loadState(): OverlayState {
    try {
        if (typeof localStorage === 'undefined') return { ...DEFAULT_OVERLAY_STATE };
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return { ...DEFAULT_OVERLAY_STATE };
        const parsed = JSON.parse(raw);
        return validateState(parsed);
    } catch {
        return { ...DEFAULT_OVERLAY_STATE };
    }
}

function persistState(state: OverlayState): void {
    try {
        if (typeof localStorage === 'undefined') return;
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
        // Quota / privacy mode — ignore. State stays in memory for the session.
    }
}

/**
 * Coerce an unknown blob into a valid `OverlayState`. Unknown fields are
 * dropped; missing fields fall back to defaults. Exposed for testing.
 */
const VALID_CROSSINGS_COLOR_MODES: ReadonlyArray<CrossingsColorMode> = ['none', 'angle', 'typePair'];

export function validateState(raw: unknown): OverlayState {
    if (!raw || typeof raw !== 'object') return { ...DEFAULT_OVERLAY_STATE };
    const r = raw as Record<string, unknown>;
    const colorBy = typeof r.crossingsColorBy === 'string'
        && (VALID_CROSSINGS_COLOR_MODES as readonly string[]).includes(r.crossingsColorBy)
        ? r.crossingsColorBy as CrossingsColorMode
        : DEFAULT_OVERLAY_STATE.crossingsColorBy;
    return {
        crossings: typeof r.crossings === 'boolean' ? r.crossings : DEFAULT_OVERLAY_STATE.crossings,
        drawingArea: typeof r.drawingArea === 'boolean' ? r.drawingArea : DEFAULT_OVERLAY_STATE.drawingArea,
        meanEdgeLine: typeof r.meanEdgeLine === 'boolean' ? r.meanEdgeLine : DEFAULT_OVERLAY_STATE.meanEdgeLine,
        stdDevLine: typeof r.stdDevLine === 'boolean' ? r.stdDevLine : DEFAULT_OVERLAY_STATE.stdDevLine,
        aspectRatio: typeof r.aspectRatio === 'boolean' ? r.aspectRatio : DEFAULT_OVERLAY_STATE.aspectRatio,
        groupCardinality: typeof r.groupCardinality === 'boolean' ? r.groupCardinality : DEFAULT_OVERLAY_STATE.groupCardinality,
        crossingsColorBy: colorBy,
        stressDistanceColoring: typeof r.stressDistanceColoring === 'boolean' ? r.stressDistanceColoring : DEFAULT_OVERLAY_STATE.stressDistanceColoring,
        stressPairDistance: typeof r.stressPairDistance === 'boolean' ? r.stressPairDistance : DEFAULT_OVERLAY_STATE.stressPairDistance,
    };
}

// =============================================================================
// Test-only escape hatch — reset module state. Production code should not
// call this; it exists so unit tests can isolate state across cases.
// =============================================================================

export function _resetForTests(): void {
    currentState = { ...DEFAULT_OVERLAY_STATE };
    isActive = false;
    elementIds = [];
    originalParentLabels = null;
}

// =============================================================================
// Modal wiring — checkbox grid + preset buttons in `index.html`
// =============================================================================

const OVERLAY_KEYS: Array<keyof OverlayState> = [
    'crossings',
    'drawingArea',
    'meanEdgeLine',
    'stdDevLine',
    'aspectRatio',
    'groupCardinality',
    'stressDistanceColoring',
    'stressPairDistance',
];

/**
 * Sync the modal's checkbox states + radio buttons to `currentState`.
 * Called every time the modal opens so the UI reflects whatever the state
 * machine currently holds.
 */
function syncModalCheckboxes(): void {
    const state = getOverlayState();
    OVERLAY_KEYS.forEach(key => {
        const cb = document.querySelector<HTMLInputElement>(`input[data-overlay-key="${key}"]`);
        if (cb) cb.checked = !!state[key];
    });
    // Crossings color mode (radio group)
    document
        .querySelectorAll<HTMLInputElement>('input[data-overlay-radio="crossingsColorBy"]')
        .forEach(r => {
            r.checked = r.value === state.crossingsColorBy;
        });
}

/**
 * Wire a single click on each checkbox / preset button. Idempotent: replaces
 * any previous handler.
 */
function wireModalControls(): void {
    OVERLAY_KEYS.forEach(key => {
        const cb = document.querySelector<HTMLInputElement>(`input[data-overlay-key="${key}"]`);
        if (!cb) return;
        cb.onchange = () => {
            setOverlayState({ [key]: cb.checked } as Partial<OverlayState>);
            // Reflect any visible button label that depends on count
            updateExternalToggleLabel();
        };
    });

    // Crossings color radio group
    document
        .querySelectorAll<HTMLInputElement>('input[data-overlay-radio="crossingsColorBy"]')
        .forEach(r => {
            r.onchange = () => {
                if (r.checked && (VALID_CROSSINGS_COLOR_MODES as readonly string[]).includes(r.value)) {
                    setOverlayState({ crossingsColorBy: r.value as CrossingsColorMode });
                }
            };
        });

    document.querySelectorAll<HTMLButtonElement>('button[data-debug-preset]').forEach(btn => {
        const name = btn.getAttribute('data-debug-preset') as PresetName | null;
        if (!name) return;
        btn.onclick = () => {
            applyPreset(name);
            syncModalCheckboxes();
            updateExternalToggleLabel();
        };
    });
}

/**
 * Refresh the Statistics-modal toggle button so its `(N)` count reflects
 * the latest state. Importer in `statistics.ts` exposes the implementation.
 */
function updateExternalToggleLabel(): void {
    const btn = document.getElementById('stats-toggle-crossings') as HTMLButtonElement | null;
    if (!btn) return;
    if (isDebugOverlayActive()) {
        btn.textContent = '❌ Hide debug overlay';
    } else {
        const n = countEnabledOverlays();
        btn.textContent = n === 0
            ? '🔍 Show debug overlay (none active)'
            : `🔍 Show debug overlay (${n})`;
    }
}

/**
 * Open the Debug Overlay settings modal. Wires the controls and syncs
 * checkbox state from `currentState` on every open so the UI is always
 * accurate even after preset clicks from a previous session.
 */
export function openDebugOverlayModal(): void {
    const modal = document.getElementById('debug-overlay-modal');
    if (!modal) return;
    wireModalControls();
    syncModalCheckboxes();
    // Re-sync stress vis listener — cy may have been recreated since
    // last bind (graph rebuild), and the prior listener was bound on
    // a destroyed instance.
    syncStressVisualizationState();
    modal.style.display = 'flex';
}

export function closeDebugOverlayModal(): void {
    const modal = document.getElementById('debug-overlay-modal');
    if (modal) modal.style.display = 'none';
}

// Expose globals for inline `onclick` handlers in index.html
if (typeof window !== 'undefined') {
    (window as unknown as Record<string, unknown>).openDebugOverlayModal = openDebugOverlayModal;
    (window as unknown as Record<string, unknown>).closeDebugOverlayModal = closeDebugOverlayModal;
    (window as unknown as Record<string, unknown>).closeStressPairPanel = hideStressPairPanel;
}

// On first import, wire stress vis handlers if either mode is already on
// (e.g. persisted from a previous session via localStorage). The cy
// instance may not exist yet — `wireStressVisualizationHandlers` no-ops
// gracefully in that case; the next `setOverlayState` call will retry.
syncStressVisualizationState();
