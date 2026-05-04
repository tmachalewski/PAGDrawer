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
    computeBoundingBox,
    computeMeanEdgeLength,
    computeEdgeLengthStd,
    computeAspectRatio,
    computeCompoundCardinality,
    type CrossingInfo,
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
}

export const DEFAULT_OVERLAY_STATE: OverlayState = {
    crossings: true,
    drawingArea: true,
    meanEdgeLine: true,
    stdDevLine: true,
    aspectRatio: false,
    groupCardinality: false,
    crossingsColorBy: 'none',
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
    },
    layout: {
        crossings: false,
        drawingArea: true,
        meanEdgeLine: true,
        stdDevLine: true,
        aspectRatio: true,
        groupCardinality: false,
        crossingsColorBy: 'none',
    },
    reductions: {
        crossings: false,
        drawingArea: false,
        meanEdgeLine: false,
        stdDevLine: false,
        aspectRatio: false,
        groupCardinality: true,
        crossingsColorBy: 'none',
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
    currentState = { ...currentState, ...partial };
    persistState(currentState);
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
}

/**
 * Remove every rendered overlay element. Restores any compound-parent labels
 * we modified for M21.
 */
export function hideDebugOverlay(): void {
    clearAll();
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
            cy.add({
                group: 'nodes',
                data: {
                    id,
                    type: 'CROSSING_DEBUG',
                    edgeA: `${c.edgeA.sourceId} → ${c.edgeA.targetId}`,
                    edgeB: `${c.edgeB.sourceId} → ${c.edgeB.targetId}`,
                    angleDeg: ((c.angle * 180) / Math.PI).toFixed(1),
                    typePair: `${c.edgeAType}×${c.edgeBType}`,
                },
                position: { x: c.point.x, y: c.point.y },
                style: color ? { 'background-color': color } : undefined,
                selectable: false,
                grabbable: false,
            });
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
}
