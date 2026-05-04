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
    computeDistanceColoringStyles,
    computeStressPairDisplay,
    _resetForTests,
    type OverlayState,
} from './debugOverlay';
import type { CrossingInfo, NodeWithPosition } from '../features/metrics';

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
            stressDistanceColoring: false,
            stressPairDistance: false,
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
            stressDistanceColoring: false,
            stressPairDistance: false,
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

    it('returns 8 when every overlay is enabled', () => {
        const all: OverlayState = {
            crossings: true,
            drawingArea: true,
            meanEdgeLine: true,
            stdDevLine: true,
            aspectRatio: true,
            groupCardinality: true,
            crossingsColorBy: 'angle',
            stressDistanceColoring: true,
            stressPairDistance: true,
        };
        expect(countEnabledOverlays(all)).toBe(8);
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
        expect((r as unknown as Record<string, unknown>).futureFlag).toBeUndefined();
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

    it('preserves stressDistanceColoring + stressPairDistance booleans', () => {
        const r = validateState({
            ...DEFAULT_OVERLAY_STATE,
            stressDistanceColoring: true,
            stressPairDistance: true,
        });
        expect(r.stressDistanceColoring).toBe(true);
        expect(r.stressPairDistance).toBe(true);
    });

    it('falls back to false for non-boolean stress visualisation flags', () => {
        const r = validateState({
            ...DEFAULT_OVERLAY_STATE,
            stressDistanceColoring: 'yes',
            stressPairDistance: 1,
        });
        expect(r.stressDistanceColoring).toBe(false);
        expect(r.stressPairDistance).toBe(false);
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

describe('stress visualisation — distance coloring (M1)', () => {
    function mkN(id: string, x = 0, y = 0): NodeWithPosition {
        return { id, x, y };
    }

    it('returns no styles when nodes list is empty', () => {
        expect(computeDistanceColoringStyles('a', [], new Map()).size).toBe(0);
    });

    it('source node gets a yellow border + black fill', () => {
        const apsp = new Map([['a', new Map([['a', 0]])]]);
        const styles = computeDistanceColoringStyles('a', [mkN('a')], apsp);
        const s = styles.get('a')!;
        expect(s['background-color']).toBe('#000000');
        expect(s['border-color']).toBe('#ffeb3b');
        expect(s['border-width']).toBe(4);
    });

    it('reachable nodes get an HSL color where 0=red and max=green', () => {
        // Source 'a', distances 1, 2, 3 → max=3 → t=1/3, 2/3, 3/3 → hue 40, 80, 120
        const nodes = [mkN('a'), mkN('b'), mkN('c'), mkN('d')];
        const apsp = new Map([
            ['a', new Map([['a', 0], ['b', 1], ['c', 2], ['d', 3]])],
            ['b', new Map([['b', 0]])],
            ['c', new Map([['c', 0]])],
            ['d', new Map([['d', 0]])],
        ]);
        const styles = computeDistanceColoringStyles('a', nodes, apsp);
        expect(styles.get('b')!['background-color']).toBe('hsl(40, 75%, 55%)');
        expect(styles.get('c')!['background-color']).toBe('hsl(80, 75%, 55%)');
        expect(styles.get('d')!['background-color']).toBe('hsl(120, 75%, 55%)');
    });

    it('unreachable nodes get translucent grey', () => {
        const nodes = [mkN('a'), mkN('z')];
        const apsp = new Map([
            ['a', new Map([['a', 0]])],
            ['z', new Map([['z', 0]])],
        ]);
        const styles = computeDistanceColoringStyles('a', nodes, apsp);
        expect(styles.get('z')!['background-color']).toBe('rgba(128, 128, 128, 0.4)');
    });

    it('symmetrises distance — node reachable in only one direction is coloured (not grey)', () => {
        const nodes = [mkN('a'), mkN('b')];
        // a → b only; no path b → a
        const apsp = new Map([
            ['a', new Map([['a', 0], ['b', 1]])],
            ['b', new Map([['b', 0]])],
        ]);
        const styles = computeDistanceColoringStyles('a', nodes, apsp);
        // 'b' should still be coloured (reachable via a → b)
        const c = styles.get('b')!['background-color'] as string;
        expect(c).not.toBe('rgba(128, 128, 128, 0.4)');
        expect(c).toMatch(/^hsl\(/);
    });
});

describe('stress visualisation — pair-distance display (M1)', () => {
    function mkN(id: string, x: number, y: number): NodeWithPosition {
        return { id, x, y };
    }

    it('formats reachable distances as numbers', () => {
        const nodes = [mkN('a', 0, 0), mkN('b', 3, 4)];
        const apsp = new Map([
            ['a', new Map([['a', 0], ['b', 1]])],
            ['b', new Map([['a', 5], ['b', 0]])],
        ]);
        const r = computeStressPairDisplay('a', 'b', nodes, apsp);
        expect(r.forwardDistance).toBe('1');
        expect(r.backwardDistance).toBe('5');
        expect(r.symmetrizedDistance).toBe('1');
        expect(r.euclideanDistance).toBe('5.0'); // sqrt(9 + 16)
    });

    it('formats unreachable directions as "unreachable"', () => {
        const nodes = [mkN('a', 0, 0), mkN('b', 1, 0)];
        // a → b only
        const apsp = new Map([
            ['a', new Map([['a', 0], ['b', 1]])],
            ['b', new Map<string, number>([['b', 0]])],
        ]);
        const r = computeStressPairDisplay('a', 'b', nodes, apsp);
        expect(r.forwardDistance).toBe('1');
        expect(r.backwardDistance).toBe('unreachable');
        expect(r.symmetrizedDistance).toBe('1'); // symmetrised falls through
        expect(r.euclideanDistance).toBe('1.0');
    });

    it('reports both directions unreachable when there is no path either way', () => {
        const nodes = [mkN('a', 0, 0), mkN('z', 99, 0)];
        const apsp = new Map([
            ['a', new Map([['a', 0]])],
            ['z', new Map([['z', 0]])],
        ]);
        const r = computeStressPairDisplay('a', 'z', nodes, apsp);
        expect(r.forwardDistance).toBe('unreachable');
        expect(r.backwardDistance).toBe('unreachable');
        expect(r.symmetrizedDistance).toBe('unreachable');
        expect(r.euclideanDistance).toBe('99.0');
    });

    it('returns "—" Euclidean when one node is missing from the nodes list', () => {
        const r = computeStressPairDisplay('a', 'b', [], new Map());
        expect(r.euclideanDistance).toBe('—');
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
