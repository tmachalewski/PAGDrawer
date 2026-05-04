/**
 * Tests for the debug-overlay state machine, preset application, and
 * localStorage round-trip. The drawing pipeline (Cytoscape pseudo-elements)
 * is not exercised here — those paths require a real cy instance and are
 * better suited to manual / integration testing.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
    DEFAULT_OVERLAY_STATE,
    PRESETS,
    getOverlayState,
    setOverlayState,
    applyPreset,
    countEnabledOverlays,
    validateState,
    isDebugOverlayActive,
    angleToColor,
    pickCrossingColor,
    buildTypePairPalette,
    _resetForTests,
    type OverlayState,
} from './debugOverlay';
import type { CrossingInfo } from '../features/metrics';

// debugOverlay.ts imports getCy at the top of the module. We don't need it
// for state-machine tests, but `setOverlayState` calls `redraw()` which
// touches `getCy()` if isActive — which we keep false in these tests, so
// the import is harmless.
vi.mock('../graph/core', () => ({
    getCy: vi.fn(() => null),
}));

const STORAGE_KEY = 'debugOverlayState_v1';

beforeEach(() => {
    localStorage.clear();
    _resetForTests();
});

describe('DEFAULT_OVERLAY_STATE', () => {
    it('enables the four existing overlays by default and disables the new ones', () => {
        expect(DEFAULT_OVERLAY_STATE).toEqual({
            crossings: true,
            drawingArea: true,
            meanEdgeLine: true,
            stdDevLine: true,
            aspectRatio: false,
            groupCardinality: false,
            crossingsColorBy: 'none',
        });
    });
});

describe('getOverlayState / setOverlayState', () => {
    it('returns a copy (mutating return value does not affect internal state)', () => {
        const a = getOverlayState();
        a.crossings = false;
        expect(getOverlayState().crossings).toBe(true);
    });

    it('setOverlayState merges partial updates onto the current state', () => {
        setOverlayState({ aspectRatio: true });
        expect(getOverlayState()).toEqual({
            ...DEFAULT_OVERLAY_STATE,
            aspectRatio: true,
        });
    });

    it('setOverlayState persists to localStorage', () => {
        setOverlayState({ groupCardinality: true });
        const raw = localStorage.getItem(STORAGE_KEY);
        expect(raw).not.toBeNull();
        expect(JSON.parse(raw!)).toEqual({
            ...DEFAULT_OVERLAY_STATE,
            groupCardinality: true,
        });
    });

    it('setOverlayState does not mutate the input partial', () => {
        const partial = { aspectRatio: true };
        setOverlayState(partial);
        expect(partial).toEqual({ aspectRatio: true });
    });
});

describe('applyPreset', () => {
    it('crossings preset enables crossings + aspectRatio only', () => {
        applyPreset('crossings');
        const s = getOverlayState();
        expect(s.crossings).toBe(true);
        expect(s.aspectRatio).toBe(true);
        expect(s.drawingArea).toBe(false);
        expect(s.meanEdgeLine).toBe(false);
        expect(s.groupCardinality).toBe(false);
    });

    it('layout preset enables bbox-related overlays + aspect ratio', () => {
        applyPreset('layout');
        const s = getOverlayState();
        expect(s.crossings).toBe(false);
        expect(s.drawingArea).toBe(true);
        expect(s.meanEdgeLine).toBe(true);
        expect(s.stdDevLine).toBe(true);
        expect(s.aspectRatio).toBe(true);
    });

    it('reductions preset enables only group cardinality', () => {
        applyPreset('reductions');
        expect(getOverlayState()).toEqual({
            crossings: false,
            drawingArea: false,
            meanEdgeLine: false,
            stdDevLine: false,
            aspectRatio: false,
            groupCardinality: true,
            crossingsColorBy: 'none',
        });
    });

    it('crossings preset turns on type-pair coloring (M25)', () => {
        applyPreset('crossings');
        expect(getOverlayState().crossingsColorBy).toBe('typePair');
    });

    it('defaults preset matches DEFAULT_OVERLAY_STATE', () => {
        // First clobber state with something else
        applyPreset('clear');
        // Now apply defaults
        applyPreset('defaults');
        expect(getOverlayState()).toEqual(DEFAULT_OVERLAY_STATE);
    });

    it('clear preset turns every boolean toggle off and color mode to "none"', () => {
        applyPreset('clear');
        const s = getOverlayState();
        expect(s.crossings).toBe(false);
        expect(s.drawingArea).toBe(false);
        expect(s.meanEdgeLine).toBe(false);
        expect(s.stdDevLine).toBe(false);
        expect(s.aspectRatio).toBe(false);
        expect(s.groupCardinality).toBe(false);
        expect(s.crossingsColorBy).toBe('none');
    });

    it('PRESETS exposes exactly the five named presets', () => {
        expect(Object.keys(PRESETS).sort()).toEqual([
            'clear', 'crossings', 'defaults', 'layout', 'reductions',
        ]);
    });

    it('preset application persists to localStorage', () => {
        applyPreset('crossings');
        const raw = JSON.parse(localStorage.getItem(STORAGE_KEY)!);
        expect(raw.crossings).toBe(true);
        expect(raw.drawingArea).toBe(false);
    });
});

describe('countEnabledOverlays', () => {
    it('returns 4 for the default state (the existing 4 overlays)', () => {
        expect(countEnabledOverlays(DEFAULT_OVERLAY_STATE)).toBe(4);
    });

    it('returns 0 for the clear preset', () => {
        expect(countEnabledOverlays(PRESETS.clear)).toBe(0);
    });

    it('returns 6 when every overlay is enabled', () => {
        const all: OverlayState = {
            crossings: true,
            drawingArea: true,
            meanEdgeLine: true,
            stdDevLine: true,
            aspectRatio: true,
            groupCardinality: true,
            crossingsColorBy: 'angle',
        };
        expect(countEnabledOverlays(all)).toBe(6);
    });

    it('does not count the crossingsColorBy radio mode (only boolean toggles)', () => {
        // crossingsColorBy is a sub-mode of `crossings`, not a separate overlay.
        // 'none' is a non-empty string and would erroneously be truthy if we
        // counted Object.values(state).filter(Boolean).
        expect(countEnabledOverlays(PRESETS.clear)).toBe(0); // even though 'none' is truthy
    });

    it('uses currentState as the default when no argument is given', () => {
        applyPreset('clear');
        expect(countEnabledOverlays()).toBe(0);
        applyPreset('defaults');
        expect(countEnabledOverlays()).toBe(4);
    });
});

describe('validateState', () => {
    it('returns defaults for null / non-object input', () => {
        expect(validateState(null)).toEqual(DEFAULT_OVERLAY_STATE);
        expect(validateState(undefined)).toEqual(DEFAULT_OVERLAY_STATE);
        expect(validateState(42)).toEqual(DEFAULT_OVERLAY_STATE);
        expect(validateState('hi')).toEqual(DEFAULT_OVERLAY_STATE);
    });

    it('fills missing fields with defaults', () => {
        expect(validateState({ crossings: false })).toEqual({
            ...DEFAULT_OVERLAY_STATE,
            crossings: false,
        });
    });

    it('drops non-boolean values for known keys (uses default instead)', () => {
        expect(validateState({ crossings: 'yes' })).toEqual(DEFAULT_OVERLAY_STATE);
        expect(validateState({ drawingArea: 1 })).toEqual(DEFAULT_OVERLAY_STATE);
    });

    it('drops unknown keys (forward-compat against schema additions)', () => {
        const r = validateState({ ...DEFAULT_OVERLAY_STATE, futureFlag: true });
        expect(r).toEqual(DEFAULT_OVERLAY_STATE);
        expect((r as Record<string, unknown>).futureFlag).toBeUndefined();
    });

    it('accepts valid crossingsColorBy values', () => {
        expect(validateState({ ...DEFAULT_OVERLAY_STATE, crossingsColorBy: 'angle' }).crossingsColorBy).toBe('angle');
        expect(validateState({ ...DEFAULT_OVERLAY_STATE, crossingsColorBy: 'typePair' }).crossingsColorBy).toBe('typePair');
        expect(validateState({ ...DEFAULT_OVERLAY_STATE, crossingsColorBy: 'none' }).crossingsColorBy).toBe('none');
    });

    it('falls back to "none" for unknown crossingsColorBy values', () => {
        expect(validateState({ ...DEFAULT_OVERLAY_STATE, crossingsColorBy: 'invalid' }).crossingsColorBy).toBe('none');
        expect(validateState({ ...DEFAULT_OVERLAY_STATE, crossingsColorBy: 42 }).crossingsColorBy).toBe('none');
    });
});

describe('localStorage round-trip', () => {
    it('writes via setOverlayState; subsequent validateState recovers it', () => {
        setOverlayState({ aspectRatio: true, groupCardinality: true });
        const raw = localStorage.getItem(STORAGE_KEY);
        expect(raw).not.toBeNull();
        const parsed = validateState(JSON.parse(raw!));
        expect(parsed.aspectRatio).toBe(true);
        expect(parsed.groupCardinality).toBe(true);
    });

    it('storage key is versioned (`debugOverlayState_v1`)', () => {
        setOverlayState({ crossings: false });
        expect(localStorage.getItem('debugOverlayState_v1')).not.toBeNull();
        // Future v2 schema would use a different key — current key reserved
        expect(localStorage.getItem('debugOverlayState_v2')).toBeNull();
    });
});

describe('isDebugOverlayActive', () => {
    it('starts inactive after reset', () => {
        expect(isDebugOverlayActive()).toBe(false);
    });
});

describe('crossings color picking (M2 + M25)', () => {
    function mkInfo(angle: number, edgeAType = 'A', edgeBType = 'B'): CrossingInfo {
        return {
            point: { x: 0, y: 0 },
            edgeA: { source: { x: 0, y: 0 }, target: { x: 1, y: 0 }, sourceId: 'a', targetId: 'b', type: edgeAType },
            edgeB: { source: { x: 0, y: 0 }, target: { x: 1, y: 1 }, sourceId: 'c', targetId: 'd', type: edgeBType },
            angle,
            edgeAType, edgeBType,
        };
    }

    describe('angleToColor (M2)', () => {
        it('returns red-ish hue at 0 (acute)', () => {
            expect(angleToColor(0)).toMatch(/^hsl\(0/);
        });
        it('returns yellow-ish hue at 45° (~hue 60)', () => {
            expect(angleToColor(Math.PI / 4)).toMatch(/^hsl\(60/);
        });
        it('returns green-ish hue at 90° (~hue 120)', () => {
            expect(angleToColor(Math.PI / 2)).toMatch(/^hsl\(120/);
        });
        it('clamps angles outside [0, π/2] (defensive)', () => {
            expect(angleToColor(-1)).toMatch(/^hsl\(0/);
            expect(angleToColor(Math.PI)).toMatch(/^hsl\(120/);
        });
    });

    describe('buildTypePairPalette (M25)', () => {
        it('orders palette slots by frequency (most-common gets index 0 = red)', () => {
            const xs = [
                mkInfo(0, 'A', 'B'), mkInfo(0, 'A', 'B'), mkInfo(0, 'A', 'B'),
                mkInfo(0, 'C', 'D'),
            ];
            const palette = buildTypePairPalette(xs);
            expect(palette.get('A×B')).toBe('#ef4444');     // first slot = red
            expect(palette.get('C×D')).toBe('#f59e0b');     // second slot
        });

        it('breaks ties on count by lex-first key', () => {
            const xs = [mkInfo(0, 'B', 'Z'), mkInfo(0, 'A', 'C')];
            const palette = buildTypePairPalette(xs);
            expect(palette.get('A×C')).toBe('#ef4444');
            expect(palette.get('B×Z')).toBe('#f59e0b');
        });
    });

    describe('pickCrossingColor', () => {
        it('returns null in "none" mode (caller leaves stylesheet default)', () => {
            const c = mkInfo(Math.PI / 4);
            expect(pickCrossingColor(c, 'none', new Map())).toBeNull();
        });

        it('returns an HSL string in "angle" mode', () => {
            const c = mkInfo(Math.PI / 2);
            expect(pickCrossingColor(c, 'angle', new Map())).toMatch(/^hsl\(120/);
        });

        it('returns the palette colour in "typePair" mode', () => {
            const c = mkInfo(0, 'A', 'B');
            const palette = new Map([['A×B', '#3b82f6']]);
            expect(pickCrossingColor(c, 'typePair', palette)).toBe('#3b82f6');
        });

        it('falls back to first palette slot for an unknown type pair', () => {
            const c = mkInfo(0, 'X', 'Y');
            expect(pickCrossingColor(c, 'typePair', new Map())).toBe('#ef4444');
        });
    });
});
