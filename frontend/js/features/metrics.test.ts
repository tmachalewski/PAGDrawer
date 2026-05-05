/**
 * Unit tests for graph drawing quality metrics.
 */

import { describe, it, expect } from 'vitest';
import {
    segmentsIntersect,
    segmentIntersectionPoint,
    countCrossings,
    findCrossings,
    normalizeCrossings,
    computeDrawingArea,
    computeBoundingBox,
    computeEdgeLengthCV,
    computeMeanEdgeLength,
    computeEdgeLengthStd,
    computeAspectRatio,
    computeCompoundCardinalityFromCounts,
    computeCrossingAngle,
    computeCrossingAngleStats,
    computeTypePairCrossingStats,
    computeAPSP,
    computeStressFromAPSP,
    symmetrizedDistance,
    computeBridgeStatsFromList,
    computeEcrFromList,
    computeAcrFromKeys,
    type NodeWithPosition,
    type BridgeEdgeInfo,
    metricsToCSV,
    metricsToJSON,
    metricsToJsonObject,
    buildMetricsJsonSnapshot,
    buildDataSourceSnapshot,
    type DrawingMetrics,
    type DataSourceSnapshot,
    type CrossingInfo,
    type EdgeEndpoints,
} from './metrics';
import type { SettingsSnapshot } from './settingsSnapshot';

// Helper to build edge records for testing
function mkEdge(
    sId: string, tId: string,
    sx: number, sy: number, tx: number, ty: number,
    type: string = '',
): EdgeEndpoints {
    return {
        source: { x: sx, y: sy },
        target: { x: tx, y: ty },
        sourceId: sId,
        targetId: tId,
        type,
    };
}

describe('segmentsIntersect', () => {
    it('detects simple crossing (+ shape)', () => {
        const p1 = { x: 0, y: 5 }, p2 = { x: 10, y: 5 };   // horizontal
        const p3 = { x: 5, y: 0 }, p4 = { x: 5, y: 10 };   // vertical
        expect(segmentsIntersect(p1, p2, p3, p4)).toBe(true);
    });

    it('returns false for parallel segments', () => {
        const p1 = { x: 0, y: 0 }, p2 = { x: 10, y: 0 };
        const p3 = { x: 0, y: 5 }, p4 = { x: 10, y: 5 };
        expect(segmentsIntersect(p1, p2, p3, p4)).toBe(false);
    });

    it('returns false for disjoint segments', () => {
        const p1 = { x: 0, y: 0 }, p2 = { x: 1, y: 1 };
        const p3 = { x: 10, y: 10 }, p4 = { x: 20, y: 20 };
        expect(segmentsIntersect(p1, p2, p3, p4)).toBe(false);
    });

    it('returns false for touching at endpoint', () => {
        // sharing exact endpoint (endpoint overlap — not strict interior crossing)
        const p1 = { x: 0, y: 0 }, p2 = { x: 5, y: 5 };
        const p3 = { x: 5, y: 5 }, p4 = { x: 10, y: 0 };
        expect(segmentsIntersect(p1, p2, p3, p4)).toBe(false);
    });

    it('detects T-crossing', () => {
        const p1 = { x: 0, y: 5 }, p2 = { x: 10, y: 5 };
        const p3 = { x: 5, y: 0 }, p4 = { x: 5, y: 5 };
        // endpoint touches — no strict interior crossing
        expect(segmentsIntersect(p1, p2, p3, p4)).toBe(false);
    });
});

describe('countCrossings', () => {
    it('K4 in a square has exactly 1 crossing (the diagonals)', () => {
        // Nodes at corners of unit square: a=(0,0), b=(1,0), c=(1,1), d=(0,1)
        // K4 edges: ab, bc, cd, da (perimeter) + ac, bd (diagonals)
        // Only the two diagonals cross; other pairs share endpoints.
        const edges = [
            mkEdge('a', 'b', 0, 0, 1, 0),
            mkEdge('b', 'c', 1, 0, 1, 1),
            mkEdge('c', 'd', 1, 1, 0, 1),
            mkEdge('d', 'a', 0, 1, 0, 0),
            mkEdge('a', 'c', 0, 0, 1, 1),
            mkEdge('b', 'd', 1, 0, 0, 1)
        ];
        expect(countCrossings(edges)).toBe(1);
    });

    it('two disjoint crossing edges (X shape) = 1 crossing', () => {
        const edges = [
            mkEdge('a', 'b', 0, 0, 10, 10),
            mkEdge('c', 'd', 0, 10, 10, 0)
        ];
        expect(countCrossings(edges)).toBe(1);
    });

    it('ignores pairs sharing an endpoint', () => {
        // a→b and a→c meet at a; they don't "cross"
        const edges = [
            mkEdge('a', 'b', 0, 0, 10, 0),
            mkEdge('a', 'c', 0, 0, 10, 10)
        ];
        expect(countCrossings(edges)).toBe(0);
    });

    it('returns 0 for single edge', () => {
        expect(countCrossings([mkEdge('a', 'b', 0, 0, 1, 1)])).toBe(0);
    });

    it('returns 0 for empty edge list', () => {
        expect(countCrossings([])).toBe(0);
    });
});

describe('normalizeCrossings', () => {
    it('returns 1.0 for 0 crossings', () => {
        const edges = [
            mkEdge('a', 'b', 0, 0, 10, 0),
            mkEdge('c', 'd', 0, 10, 10, 10)
        ];
        expect(normalizeCrossings(0, edges)).toBe(1.0);
    });

    it('returns 0.0 when all possible crossings occur', () => {
        // 2 disjoint edges, 1 non-adjacent pair, 1 crossing → normalized 0.0
        const edges = [
            mkEdge('a', 'b', 0, 0, 10, 10),
            mkEdge('c', 'd', 0, 10, 10, 0)
        ];
        expect(normalizeCrossings(1, edges)).toBe(0.0);
    });

    it('returns 1.0 for fewer than 2 edges', () => {
        expect(normalizeCrossings(0, [])).toBe(1.0);
        expect(normalizeCrossings(0, [mkEdge('a', 'b', 0, 0, 1, 1)])).toBe(1.0);
    });

    it('returns 1.0 when all edge pairs share a node (max_possible = 0)', () => {
        // Star graph: all edges share the center node
        const edges = [
            mkEdge('a', 'b', 0, 0, 1, 0),
            mkEdge('a', 'c', 0, 0, 0, 1),
            mkEdge('a', 'd', 0, 0, -1, 0)
        ];
        expect(normalizeCrossings(0, edges)).toBe(1.0);
    });
});

describe('computeDrawingArea', () => {
    it('returns 0 for 0 or 1 node', () => {
        expect(computeDrawingArea([])).toBe(0);
        expect(computeDrawingArea([{ x: 5, y: 5 }])).toBe(0);
    });

    it('computes width × height for two points', () => {
        const area = computeDrawingArea([{ x: 0, y: 0 }, { x: 10, y: 20 }]);
        expect(area).toBe(200);
    });

    it('uses extrema across many points', () => {
        const pts = [
            { x: 0, y: 0 },
            { x: 5, y: 5 },
            { x: 100, y: 3 },
            { x: 40, y: 50 }
        ];
        // min_x=0, max_x=100, min_y=0, max_y=50 → 100 * 50 = 5000
        expect(computeDrawingArea(pts)).toBe(5000);
    });

    it('returns 0 when all points are collinear on one axis', () => {
        // all y=5 → bounding box height = 0
        expect(computeDrawingArea([{ x: 0, y: 5 }, { x: 10, y: 5 }])).toBe(0);
    });
});

describe('computeEdgeLengthCV', () => {
    it('returns 0 for empty edge list', () => {
        expect(computeEdgeLengthCV([])).toBe(0);
    });

    it('returns 0 when all edge lengths are equal', () => {
        const edges = [
            mkEdge('a', 'b', 0, 0, 10, 0),
            mkEdge('c', 'd', 0, 10, 10, 10),
            mkEdge('e', 'f', 0, 20, 10, 20)
        ];
        expect(computeEdgeLengthCV(edges)).toBeCloseTo(0, 10);
    });

    it('returns std/mean for varied lengths', () => {
        // lengths: 2, 4, 6 → mean=4, std=√(8/3)≈1.633, cv≈0.408
        const edges = [
            mkEdge('a', 'b', 0, 0, 2, 0),
            mkEdge('c', 'd', 0, 0, 4, 0),
            mkEdge('e', 'f', 0, 0, 6, 0)
        ];
        const cv = computeEdgeLengthCV(edges);
        expect(cv).toBeCloseTo(0.408, 2);
    });

    it('returns 0 when mean length is 0 (degenerate)', () => {
        const edges = [mkEdge('a', 'b', 5, 5, 5, 5)];
        expect(computeEdgeLengthCV(edges)).toBe(0);
    });
});

describe('segmentIntersectionPoint', () => {
    it('returns the crossing point for a + shape', () => {
        const p = segmentIntersectionPoint(
            { x: 0, y: 5 }, { x: 10, y: 5 },
            { x: 5, y: 0 }, { x: 5, y: 10 }
        );
        expect(p).not.toBeNull();
        expect(p!.x).toBeCloseTo(5, 6);
        expect(p!.y).toBeCloseTo(5, 6);
    });

    it('returns null for parallel segments', () => {
        const p = segmentIntersectionPoint(
            { x: 0, y: 0 }, { x: 10, y: 0 },
            { x: 0, y: 5 }, { x: 10, y: 5 }
        );
        expect(p).toBeNull();
    });

    it('returns null for endpoint-only touch', () => {
        const p = segmentIntersectionPoint(
            { x: 0, y: 0 }, { x: 5, y: 5 },
            { x: 5, y: 5 }, { x: 10, y: 0 }
        );
        expect(p).toBeNull();
    });
});

describe('findCrossings', () => {
    it('returns both the point and the two edges', () => {
        const edges = [
            mkEdge('a', 'b', 0, 0, 10, 10),
            mkEdge('c', 'd', 0, 10, 10, 0)
        ];
        const result = findCrossings(edges);
        expect(result.length).toBe(1);
        expect(result[0].point.x).toBeCloseTo(5, 6);
        expect(result[0].point.y).toBeCloseTo(5, 6);
        expect(result[0].edgeA.sourceId).toBe('a');
        expect(result[0].edgeB.sourceId).toBe('c');
    });

    it('agrees with countCrossings on count', () => {
        const edges = [
            mkEdge('a', 'b', 0, 0, 1, 0),
            mkEdge('b', 'c', 1, 0, 1, 1),
            mkEdge('c', 'd', 1, 1, 0, 1),
            mkEdge('d', 'a', 0, 1, 0, 0),
            mkEdge('a', 'c', 0, 0, 1, 1),
            mkEdge('b', 'd', 1, 0, 0, 1)
        ];
        expect(findCrossings(edges).length).toBe(countCrossings(edges));
    });
});

describe('computeBoundingBox', () => {
    it('returns null for empty points', () => {
        expect(computeBoundingBox([])).toBeNull();
    });

    it('returns correct min/max for multiple points', () => {
        const bb = computeBoundingBox([
            { x: 10, y: 5 }, { x: -3, y: 20 }, { x: 7, y: 0 }
        ]);
        expect(bb).toEqual({ minX: -3, maxX: 10, minY: 0, maxY: 20 });
    });
});

describe('computeMeanEdgeLength', () => {
    it('returns 0 for empty edges', () => {
        expect(computeMeanEdgeLength([])).toBe(0);
    });

    it('averages Euclidean distances', () => {
        const edges = [
            mkEdge('a', 'b', 0, 0, 3, 4),   // length 5
            mkEdge('c', 'd', 0, 0, 6, 8)    // length 10
        ];
        expect(computeMeanEdgeLength(edges)).toBeCloseTo(7.5, 6);
    });
});

describe('computeEdgeLengthStd', () => {
    it('returns 0 for empty edges', () => {
        expect(computeEdgeLengthStd([])).toBe(0);
    });

    it('returns 0 for uniform lengths', () => {
        const edges = [
            mkEdge('a', 'b', 0, 0, 5, 0),
            mkEdge('c', 'd', 0, 0, 5, 0)
        ];
        expect(computeEdgeLengthStd(edges)).toBeCloseTo(0, 6);
    });

    it('computes population std dev', () => {
        // lengths: 2, 4, 6 → mean=4, variance=(4+0+4)/3=8/3, std=√(8/3)≈1.633
        const edges = [
            mkEdge('a', 'b', 0, 0, 2, 0),
            mkEdge('c', 'd', 0, 0, 4, 0),
            mkEdge('e', 'f', 0, 0, 6, 0)
        ];
        expect(computeEdgeLengthStd(edges)).toBeCloseTo(Math.sqrt(8 / 3), 4);
    });
});

describe('computeCrossingAngle (M2)', () => {
    it('returns π/2 for perpendicular edges', () => {
        const a = mkEdge('a', 'b', 0, 0, 10, 0);     // horizontal
        const b = mkEdge('c', 'd', 5, -5, 5, 5);     // vertical
        expect(computeCrossingAngle(a, b)).toBeCloseTo(Math.PI / 2, 6);
    });

    it('is invariant to edge direction (source/target swap)', () => {
        const a = mkEdge('a', 'b', 0, 0, 10, 0);
        const b = mkEdge('c', 'd', 5, -5, 5, 5);
        const bRev = mkEdge('d', 'c', 5, 5, 5, -5);
        expect(computeCrossingAngle(a, b)).toBeCloseTo(computeCrossingAngle(a, bRev), 6);
    });

    it('returns π/4 for a 45° crossing', () => {
        const a = mkEdge('a', 'b', 0, 0, 10, 0);
        const b = mkEdge('c', 'd', 0, -5, 10, 5);    // 45° slope
        expect(computeCrossingAngle(a, b)).toBeCloseTo(Math.PI / 4, 6);
    });

    it('returns 0 for parallel edges', () => {
        const a = mkEdge('a', 'b', 0, 0, 10, 0);
        const b = mkEdge('c', 'd', 0, 5, 10, 5);
        expect(computeCrossingAngle(a, b)).toBe(0);
    });

    it('returns 0 for a degenerate (zero-length) edge', () => {
        const a = mkEdge('a', 'b', 5, 5, 5, 5);      // zero length
        const b = mkEdge('c', 'd', 0, 0, 10, 10);
        expect(computeCrossingAngle(a, b)).toBe(0);
    });
});

describe('computeCrossingAngleStats (M2)', () => {
    function mkCrossing(angle: number, edgeAType = '', edgeBType = ''): CrossingInfo {
        return {
            point: { x: 0, y: 0 },
            edgeA: mkEdge('a', 'b', 0, 0, 1, 0, edgeAType),
            edgeB: mkEdge('c', 'd', 0, 0, 1, 1, edgeBType),
            angle,
            edgeAType, edgeBType,
        };
    }

    it('returns zeros for empty input', () => {
        expect(computeCrossingAngleStats([])).toEqual({
            meanRad: 0, minRad: 0, rightAngleRatio: 0,
        });
    });

    it('computes mean and min over a small set', () => {
        const xs = [mkCrossing(Math.PI / 6), mkCrossing(Math.PI / 3), mkCrossing(Math.PI / 2)];
        const r = computeCrossingAngleStats(xs);
        expect(r.meanRad).toBeCloseTo((Math.PI / 6 + Math.PI / 3 + Math.PI / 2) / 3, 6);
        expect(r.minRad).toBeCloseTo(Math.PI / 6, 6);
    });

    it('right-angle ratio counts crossings within ±15° of 90°', () => {
        // 76°, 80°, 90°, 89° all in window (folded crossing angles ≤ 90°)
        const xs = [76, 80, 90, 89].map(d => mkCrossing(d * Math.PI / 180));
        expect(computeCrossingAngleStats(xs).rightAngleRatio).toBe(1.0);

        // 30° is outside the ±15° window → 0/1
        expect(computeCrossingAngleStats([mkCrossing(Math.PI / 6)]).rightAngleRatio).toBe(0);

        // Mixed: 30°, 80°, 89°, 30° → 2 of 4 within window
        const mixed = [30, 80, 89, 30].map(d => mkCrossing(d * Math.PI / 180));
        expect(computeCrossingAngleStats(mixed).rightAngleRatio).toBe(0.5);
    });

    it('respects a custom tolerance argument', () => {
        const c = mkCrossing((90 - 20) * Math.PI / 180);  // 70° — outside default 15°
        expect(computeCrossingAngleStats([c]).rightAngleRatio).toBe(0);
        expect(computeCrossingAngleStats([c], 25 * Math.PI / 180).rightAngleRatio).toBe(1);
    });
});

describe('computeTypePairCrossingStats (M25)', () => {
    function mkCrossing(edgeAType: string, edgeBType: string): CrossingInfo {
        return {
            point: { x: 0, y: 0 },
            edgeA: mkEdge('a', 'b', 0, 0, 1, 0, edgeAType),
            edgeB: mkEdge('c', 'd', 0, 0, 1, 1, edgeBType),
            angle: Math.PI / 4,
            edgeAType, edgeBType,
        };
    }

    it('returns zeros + empty for empty input', () => {
        expect(computeTypePairCrossingStats([])).toEqual({
            distribution: {}, topPairLabel: '', topPairShare: 0,
        });
    });

    it('counts a type-pair distribution and reports top pair', () => {
        const xs = [
            mkCrossing('HAS_VULN', 'LEADS_TO'),
            mkCrossing('HAS_VULN', 'LEADS_TO'),
            mkCrossing('HAS_VULN', 'LEADS_TO'),
            mkCrossing('HAS_VULN', 'ENABLES'),
            mkCrossing('HAS_VULN', 'ENABLES'),
        ];
        const r = computeTypePairCrossingStats(xs);
        expect(r.distribution).toEqual({
            'HAS_VULN×LEADS_TO': 3,
            'HAS_VULN×ENABLES': 2,
        });
        expect(r.topPairLabel).toBe('HAS_VULN×LEADS_TO');
        expect(r.topPairShare).toBe(0.6);
    });

    it('breaks ties by lexicographic key (deterministic)', () => {
        // Two pairs at count 1 each: lex-first wins
        const xs = [
            mkCrossing('B_TYPE', 'Z_TYPE'),
            mkCrossing('A_TYPE', 'C_TYPE'),
        ];
        const r = computeTypePairCrossingStats(xs);
        expect(r.topPairLabel).toBe('A_TYPE×C_TYPE');
        expect(r.topPairShare).toBe(0.5);
    });
});

describe('findCrossings — type-pair sorting (M25 input)', () => {
    it('sorts edge type pair lexicographically so {(A,B), (B,A)} collapse', () => {
        const a = mkEdge('a', 'b', 0, 0, 10, 0, 'B_TYPE');
        const b = mkEdge('c', 'd', 5, -5, 5, 5, 'A_TYPE');
        const xs = findCrossings([a, b]);
        expect(xs).toHaveLength(1);
        expect(xs[0].edgeAType).toBe('A_TYPE');
        expect(xs[0].edgeBType).toBe('B_TYPE');
    });

    it('attaches the computed angle to each CrossingInfo', () => {
        const a = mkEdge('a', 'b', 0, 0, 10, 0);
        const b = mkEdge('c', 'd', 5, -5, 5, 5);
        const xs = findCrossings([a, b]);
        expect(xs[0].angle).toBeCloseTo(Math.PI / 2, 6);
    });
});

describe('computeAPSP (BFS, unweighted)', () => {
    function mkE(s: string, t: string) {
        return { sourceId: s, targetId: t };
    }

    it('returns empty for empty input', () => {
        expect(computeAPSP([], []).size).toBe(0);
    });

    it('reports 0 self-distance for every node', () => {
        const apsp = computeAPSP(['a', 'b'], [mkE('a', 'b')]);
        expect(apsp.get('a')!.get('a')).toBe(0);
        expect(apsp.get('b')!.get('b')).toBe(0);
    });

    describe('directed mode (default)', () => {
        it('only follows source → target', () => {
            const apsp = computeAPSP(['a', 'b', 'c'], [mkE('a', 'b'), mkE('b', 'c')]);
            // Forward distances: present
            expect(apsp.get('a')!.get('b')).toBe(1);
            expect(apsp.get('a')!.get('c')).toBe(2);
            expect(apsp.get('b')!.get('c')).toBe(1);
            // Backward distances: NOT present
            expect(apsp.get('b')!.has('a')).toBe(false);
            expect(apsp.get('c')!.has('a')).toBe(false);
            expect(apsp.get('c')!.has('b')).toBe(false);
        });

        it('reachable in only one direction (DAG case)', () => {
            // a → b but no path b → a in directed mode
            const apsp = computeAPSP(['a', 'b'], [mkE('a', 'b')]);
            expect(apsp.get('a')!.get('b')).toBe(1);
            expect(apsp.get('b')!.has('a')).toBe(false);
        });

        it('omits unreachable pairs from the inner map', () => {
            // Two disconnected components: {a, b} and {c, d}
            const apsp = computeAPSP(
                ['a', 'b', 'c', 'd'],
                [mkE('a', 'b'), mkE('c', 'd')],
            );
            expect(apsp.get('a')!.has('c')).toBe(false);
            expect(apsp.get('a')!.has('d')).toBe(false);
            expect(apsp.get('a')!.get('b')).toBe(1);
            expect(apsp.get('c')!.get('d')).toBe(1);
        });

        it('skips edges with endpoints not in nodeIds', () => {
            const apsp = computeAPSP(['a', 'b'], [mkE('a', 'b'), mkE('a', 'orphan')]);
            expect(apsp.get('a')!.has('orphan')).toBe(false);
            expect(apsp.get('a')!.get('b')).toBe(1);
        });

        it('handles self-loops by ignoring them', () => {
            const apsp = computeAPSP(['a', 'b'], [mkE('a', 'a'), mkE('a', 'b')]);
            expect(apsp.get('a')!.get('b')).toBe(1);
        });

        it('reports correct distances on a directed 4-cycle', () => {
            // a → b → c → d → a, all directed; from a, all reachable forward
            const apsp = computeAPSP(
                ['a', 'b', 'c', 'd'],
                [mkE('a', 'b'), mkE('b', 'c'), mkE('c', 'd'), mkE('d', 'a')],
            );
            expect(apsp.get('a')!.get('b')).toBe(1);
            expect(apsp.get('a')!.get('c')).toBe(2);
            expect(apsp.get('a')!.get('d')).toBe(3);
            // cycle eventually wraps back, distance from b to a is 3
            expect(apsp.get('b')!.get('a')).toBe(3);
        });
    });

    describe('undirected mode (opt-in)', () => {
        it('treats edges as undirected when options.directed = false', () => {
            const apsp = computeAPSP(
                ['a', 'b', 'c'],
                [mkE('a', 'b'), mkE('b', 'c')],
                { directed: false },
            );
            expect(apsp.get('a')!.get('c')).toBe(2);
            expect(apsp.get('c')!.get('a')).toBe(2); // backward, only with undirected
            expect(apsp.get('b')!.get('a')).toBe(1);
        });
    });
});

describe('symmetrizedDistance', () => {
    it('returns the smaller of two directed distances', () => {
        const apsp = new Map([
            ['a', new Map([['b', 1]])],
            ['b', new Map([['a', 5]])],
        ]);
        expect(symmetrizedDistance(apsp, 'a', 'b')).toBe(1);
        expect(symmetrizedDistance(apsp, 'b', 'a')).toBe(1);
    });

    it('returns the only available distance when one direction is missing', () => {
        const apsp = new Map([
            ['a', new Map([['b', 3]])],
            ['b', new Map<string, number>()],
        ]);
        expect(symmetrizedDistance(apsp, 'a', 'b')).toBe(3);
        expect(symmetrizedDistance(apsp, 'b', 'a')).toBe(3);
    });

    it('returns undefined when neither direction is reachable', () => {
        const apsp = new Map([
            ['a', new Map<string, number>()],
            ['b', new Map<string, number>()],
        ]);
        expect(symmetrizedDistance(apsp, 'a', 'b')).toBeUndefined();
    });

    it('handles missing source node id (defensive)', () => {
        const apsp = new Map([
            ['a', new Map([['b', 1]])],
        ]);
        // 'b' is referenced as a target but has no own row — treat as
        // "no path from b to a known"
        expect(symmetrizedDistance(apsp, 'a', 'b')).toBe(1);
        expect(symmetrizedDistance(apsp, 'b', 'a')).toBe(1);
    });
});

describe('computeStressFromAPSP (M1)', () => {
    function mkN(id: string, x: number, y: number): NodeWithPosition {
        return { id, x, y };
    }

    it('returns zeros for empty / single-node input', () => {
        expect(computeStressFromAPSP([], new Map())).toEqual({
            stressPerPair: 0, stressUnreachablePairs: 0, reachablePairCount: 0,
        });
        expect(computeStressFromAPSP([mkN('a', 0, 0)], new Map())).toEqual({
            stressPerPair: 0, stressUnreachablePairs: 0, reachablePairCount: 0,
        });
    });

    it('returns 0 stress when layout distance equals graph distance for every pair', () => {
        // Two nodes 1 unit apart, graph distance 1 → diff 0 → stress 0
        const nodes = [mkN('a', 0, 0), mkN('b', 1, 0)];
        const apsp = new Map([
            ['a', new Map([['a', 0], ['b', 1]])],
            ['b', new Map([['a', 1], ['b', 0]])],
        ]);
        const r = computeStressFromAPSP(nodes, apsp);
        expect(r.stressPerPair).toBe(0);
        expect(r.reachablePairCount).toBe(1);
        expect(r.stressUnreachablePairs).toBe(0);
    });

    it('squared difference: layout 5, graph 1 → contribution = 16', () => {
        const nodes = [mkN('a', 0, 0), mkN('b', 5, 0)];
        const apsp = new Map([
            ['a', new Map([['a', 0], ['b', 1]])],
            ['b', new Map([['a', 1], ['b', 0]])],
        ]);
        const r = computeStressFromAPSP(nodes, apsp);
        // (5 - 1)^2 / 1 = 16
        expect(r.stressPerPair).toBeCloseTo(16, 6);
    });

    it('counts unreachable pairs (skip-and-report convention)', () => {
        // a-b connected, c isolated
        const nodes = [mkN('a', 0, 0), mkN('b', 1, 0), mkN('c', 99, 99)];
        const apsp = new Map([
            ['a', new Map([['a', 0], ['b', 1]])],
            ['b', new Map([['a', 1], ['b', 0]])],
            ['c', new Map([['c', 0]])],
        ]);
        const r = computeStressFromAPSP(nodes, apsp);
        // (a,b) reachable; (a,c) and (b,c) both unreachable
        expect(r.reachablePairCount).toBe(1);
        expect(r.stressUnreachablePairs).toBe(2);
    });

    it('iterates only the upper triangle (each pair counted once)', () => {
        // 3 nodes all connected, layout matches graph perfectly
        const nodes = [mkN('a', 0, 0), mkN('b', 1, 0), mkN('c', 2, 0)];
        const apsp = new Map([
            ['a', new Map([['a', 0], ['b', 1], ['c', 2]])],
            ['b', new Map([['a', 1], ['b', 0], ['c', 1]])],
            ['c', new Map([['a', 2], ['b', 1], ['c', 0]])],
        ]);
        const r = computeStressFromAPSP(nodes, apsp);
        expect(r.reachablePairCount).toBe(3); // C(3,2) = 3, NOT 6
    });

    it('stress per pair averages over reachable pairs only', () => {
        // 3 nodes: (a,b) diff 0, (a,c) diff 0, (b,c) unreachable
        const nodes = [mkN('a', 0, 0), mkN('b', 1, 0), mkN('c', 2, 0)];
        const apsp = new Map([
            ['a', new Map([['a', 0], ['b', 1], ['c', 2]])],
            ['b', new Map([['a', 1], ['b', 0]])],          // no path to c
            ['c', new Map([['a', 2], ['c', 0]])],
        ]);
        const r = computeStressFromAPSP(nodes, apsp);
        expect(r.reachablePairCount).toBe(2);
        expect(r.stressUnreachablePairs).toBe(1);
        expect(r.stressPerPair).toBe(0); // both reachable pairs match perfectly
    });

    it('symmetrises directed APSP for stress (DAG case)', () => {
        // a → b in the directed APSP; no path back. The pair is still
        // reachable for the purposes of stress (Euclidean is symmetric).
        const nodes = [mkN('a', 0, 0), mkN('b', 1, 0)];
        const apsp = new Map([
            ['a', new Map([['a', 0], ['b', 1]])],
            ['b', new Map<string, number>([['b', 0]])],   // no entry for 'a'
        ]);
        const r = computeStressFromAPSP(nodes, apsp);
        expect(r.reachablePairCount).toBe(1);
        expect(r.stressUnreachablePairs).toBe(0);
        expect(r.stressPerPair).toBe(0);  // layout matches graph
    });

    it('treats pair as unreachable only when neither direction has a path', () => {
        // Two components with only intra-component edges: (a,b) and (c)
        const nodes = [mkN('a', 0, 0), mkN('b', 1, 0), mkN('c', 9, 9)];
        const apsp = new Map([
            ['a', new Map([['a', 0], ['b', 1]])],
            ['b', new Map([['b', 0]])],
            ['c', new Map([['c', 0]])],
        ]);
        const r = computeStressFromAPSP(nodes, apsp);
        // (a,b) reachable in one direction → reachable for stress.
        // (a,c) and (b,c) unreachable in both directions → unreachable.
        expect(r.reachablePairCount).toBe(1);
        expect(r.stressUnreachablePairs).toBe(2);
    });

    describe('layoutScale parameter (normalisation)', () => {
        const nodes = [mkN('a', 0, 0), mkN('b', 10, 0)];
        const apsp = new Map([
            ['a', new Map([['a', 0], ['b', 1]])],
            ['b', new Map([['a', 1], ['b', 0]])],
        ]);

        it('default scale=1 reproduces raw stress', () => {
            // (10 - 1)² = 81
            expect(computeStressFromAPSP(nodes, apsp).stressPerPair).toBeCloseTo(81, 6);
        });

        it('scale=10 (e.g. mean edge length) gives layout_dist=1, matches d_ij → stress 0', () => {
            // (10/10 - 1)² = 0
            expect(computeStressFromAPSP(nodes, apsp, 10).stressPerPair).toBeCloseTo(0, 6);
        });

        it('scale=2 → layout_dist=5, (5-1)² = 16', () => {
            expect(computeStressFromAPSP(nodes, apsp, 2).stressPerPair).toBeCloseTo(16, 6);
        });

        it('rejects non-positive scale (returns 0 stress, still counts pairs)', () => {
            const r = computeStressFromAPSP(nodes, apsp, 0);
            expect(r.stressPerPair).toBe(0);
            expect(r.reachablePairCount).toBe(1); // pair-counting still works
        });

        it('rejects NaN and negative scale defensively', () => {
            expect(computeStressFromAPSP(nodes, apsp, NaN).stressPerPair).toBe(0);
            expect(computeStressFromAPSP(nodes, apsp, -1).stressPerPair).toBe(0);
        });

        it('Infinity scale is mathematically valid: layout_dist effectively 0, stress = mean of d_ij²', () => {
            // 1/∞ = 0, then (0 - 1)² = 1. One pair → mean = 1.
            expect(computeStressFromAPSP(nodes, apsp, Infinity).stressPerPair).toBe(1);
        });
    });
});

describe('computeBridgeStatsFromList (M19)', () => {
    function mkE(isBridge: boolean, chainLength = 0): BridgeEdgeInfo {
        return { isBridge, chainLength };
    }

    it('returns zeros for empty input', () => {
        expect(computeBridgeStatsFromList([])).toEqual({
            bridgeEdgeProportion: 0,
            meanContractionDepth: 0,
            bridgeEdgeCount: 0,
            chainLengthDistribution: {},
        });
    });

    it('returns zeros when there are no bridges among the edges', () => {
        const r = computeBridgeStatsFromList([mkE(false), mkE(false), mkE(false)]);
        expect(r.bridgeEdgeProportion).toBe(0);
        expect(r.meanContractionDepth).toBe(0);
        expect(r.bridgeEdgeCount).toBe(0);
    });

    it('counts bridges and computes proportion correctly', () => {
        // 5 edges, 2 of which are bridges → proportion 0.4
        const edges = [
            mkE(true, 1), mkE(true, 2),
            mkE(false), mkE(false), mkE(false),
        ];
        const r = computeBridgeStatsFromList(edges);
        expect(r.bridgeEdgeProportion).toBe(0.4);
        expect(r.bridgeEdgeCount).toBe(2);
        expect(r.meanContractionDepth).toBe(1.5);
    });

    it('emits a chain_length distribution', () => {
        const edges = [
            mkE(true, 1), mkE(true, 1), mkE(true, 1),  // 3 single-hop
            mkE(true, 2), mkE(true, 2),                 // 2 double-hop
            mkE(false), mkE(false),                     // 2 originals
        ];
        const r = computeBridgeStatsFromList(edges);
        expect(r.chainLengthDistribution).toEqual({ 1: 3, 2: 2 });
    });

    it('mean contraction depth is bridge-only (originals do not dilute)', () => {
        // 1 bridge with chain_length=5, 100 originals → mean is 5, not 5/101
        const edges: BridgeEdgeInfo[] = [mkE(true, 5)];
        for (let i = 0; i < 100; i++) edges.push(mkE(false));
        const r = computeBridgeStatsFromList(edges);
        expect(r.meanContractionDepth).toBe(5);
    });
});

describe('computeEcrFromList (M20)', () => {
    it('returns zeros for empty input', () => {
        expect(computeEcrFromList([])).toEqual({
            meanEcrWeighted: 0,
            compoundsCount: 0,
            perCompound: [],
        });
    });

    it('excludes compounds with zero synthetic edges', () => {
        // p1 has synthetics → included; p2 has none → excluded
        const r = computeEcrFromList([
            { parentId: 'p1', rawEdges: 12, syntheticEdges: 4, childCount: 3 },
            { parentId: 'p2', rawEdges: 5,  syntheticEdges: 0, childCount: 2 },
        ]);
        expect(r.compoundsCount).toBe(1);
        expect(r.perCompound[0].parentId).toBe('p1');
        expect(r.perCompound[0].ecr).toBe(3); // 12/4
    });

    it('computes size-weighted mean ECR', () => {
        // p1: ECR=3, weight=10
        // p2: ECR=1, weight=5
        // weighted mean = (3·10 + 1·5) / (10+5) = 35/15 ≈ 2.333
        const r = computeEcrFromList([
            { parentId: 'p1', rawEdges: 30, syntheticEdges: 10, childCount: 10 },
            { parentId: 'p2', rawEdges: 5,  syntheticEdges: 5,  childCount: 5 },
        ]);
        expect(r.meanEcrWeighted).toBeCloseTo(35 / 15, 6);
    });

    it('falls back to zero when total weight is zero (all-singleton compounds with synth edges and child=0)', () => {
        // edge case — childCount: 0 should not divide by zero
        const r = computeEcrFromList([
            { parentId: 'p1', rawEdges: 5, syntheticEdges: 1, childCount: 0 },
        ]);
        expect(r.meanEcrWeighted).toBe(0);
    });
});

describe('computeAcrFromKeys (M22)', () => {
    function mkCve(
        prereqs: { AV?: string; AC?: string; PR?: string; UI?: string } | null,
        vc_outcomes: ReadonlyArray<readonly [string, string]> | null,
        chain_depth = 0,
        layer = 'L1',
    ) {
        return { prereqs, vc_outcomes, chain_depth, layer };
    }

    it('returns zeros for empty input', () => {
        expect(computeAcrFromKeys([])).toEqual({
            acrPrereqs: 0, acrOutcomes: 0, nodeCount: 0,
        });
    });

    it('ACR=1.0 when every CVE has a unique prereq AND outcome key', () => {
        const cves = [
            mkCve({ AV: 'N', AC: 'L', PR: 'N', UI: 'N' }, [['A', 'L']]),
            mkCve({ AV: 'L', AC: 'H', PR: 'L', UI: 'R' }, [['B', 'L']]),
            mkCve({ AV: 'A', AC: 'L', PR: 'N', UI: 'N' }, [['C', 'L']]),
        ];
        const r = computeAcrFromKeys(cves);
        expect(r.acrPrereqs).toBe(1.0);
        expect(r.acrOutcomes).toBe(1.0);
        expect(r.nodeCount).toBe(3);
    });

    it('ACR < 1 when CVEs share keys', () => {
        // 4 CVEs, only 2 distinct prereq-keys → acrPrereqs = 0.5
        const cves = [
            mkCve({ AV: 'N', AC: 'L', PR: 'N', UI: 'N' }, [['A', 'L']]),
            mkCve({ AV: 'N', AC: 'L', PR: 'N', UI: 'N' }, [['B', 'L']]),
            mkCve({ AV: 'L', AC: 'H', PR: 'L', UI: 'R' }, [['A', 'L']]),
            mkCve({ AV: 'L', AC: 'H', PR: 'L', UI: 'R' }, [['A', 'L']]),
        ];
        const r = computeAcrFromKeys(cves);
        // Distinct prereq keys: 2 ({N,L,N,N}, {L,H,L,R}) over 4 CVEs → 0.5
        expect(r.acrPrereqs).toBe(0.5);
        // Distinct outcome keys: 2 ([A,L], [B,L]) over 4 CVEs → 0.5
        expect(r.acrOutcomes).toBe(0.5);
        expect(r.nodeCount).toBe(4);
    });

    it('layer separates otherwise-identical keys', () => {
        // Same prereqs but different layers → 2 distinct keys, ACR=1.0
        const cves = [
            mkCve({ AV: 'N', AC: 'L', PR: 'N', UI: 'N' }, [['A', 'L']], 0, 'L1'),
            mkCve({ AV: 'N', AC: 'L', PR: 'N', UI: 'N' }, [['A', 'L']], 0, 'L2'),
        ];
        const r = computeAcrFromKeys(cves);
        expect(r.acrPrereqs).toBe(1.0);
        expect(r.acrOutcomes).toBe(1.0);
    });

    it('chain_depth separates otherwise-identical keys', () => {
        const cves = [
            mkCve({ AV: 'N', AC: 'L', PR: 'N', UI: 'N' }, [['A', 'L']], 0),
            mkCve({ AV: 'N', AC: 'L', PR: 'N', UI: 'N' }, [['A', 'L']], 1),
        ];
        const r = computeAcrFromKeys(cves);
        expect(r.acrPrereqs).toBe(1.0);
        expect(r.acrOutcomes).toBe(1.0);
    });

    it('null prereqs / outcomes get a sentinel "unknown" key shared across nulls', () => {
        // Three CVEs with null prereqs at the same layer/depth → all collapse
        // into one "unknown" key → acrPrereqs = 1/3
        const cves = [
            mkCve(null, [['A', 'L']]),
            mkCve(null, [['B', 'L']]),
            mkCve(null, [['C', 'L']]),
        ];
        const r = computeAcrFromKeys(cves);
        expect(r.acrPrereqs).toBeCloseTo(1 / 3, 6);
        expect(r.acrOutcomes).toBe(1.0);  // all distinct outcomes
    });

    it('outcomes-mode: empty outcomes array shares the "none" sentinel', () => {
        // Three CVEs with empty outcomes → all collapse to "none|L1|d0"
        const cves = [
            mkCve({ AV: 'N', AC: 'L', PR: 'N', UI: 'N' }, []),
            mkCve({ AV: 'L', AC: 'H', PR: 'L', UI: 'R' }, []),
            mkCve({ AV: 'A', AC: 'L', PR: 'N', UI: 'N' }, []),
        ];
        const r = computeAcrFromKeys(cves);
        expect(r.acrPrereqs).toBe(1.0);  // distinct prereqs
        expect(r.acrOutcomes).toBeCloseTo(1 / 3, 6);  // all "none|L1|d0"
    });

    it('orders sensitivity: outcomes are NOT sorted by the metric (backend pre-sorts)', () => {
        // Same outcome list in different orders should produce DIFFERENT keys
        // (the backend sorts before storage; we trust that contract).
        const cves = [
            mkCve(null, [['A', 'L'], ['B', 'L']]),
            mkCve(null, [['B', 'L'], ['A', 'L']]),
        ];
        const r = computeAcrFromKeys(cves);
        expect(r.acrOutcomes).toBe(1.0);  // 2 distinct keys
    });
});

describe('computeAspectRatio (M9)', () => {
    it('returns 1 for a square bbox', () => {
        expect(computeAspectRatio({ minX: 0, maxX: 10, minY: 0, maxY: 10 })).toBe(1);
    });

    it('returns 0.5 for a 2:1 rectangle (any orientation)', () => {
        expect(computeAspectRatio({ minX: 0, maxX: 20, minY: 0, maxY: 10 })).toBe(0.5);
        expect(computeAspectRatio({ minX: 0, maxX: 10, minY: 0, maxY: 20 })).toBe(0.5);
    });

    it('returns 0 for null bbox', () => {
        expect(computeAspectRatio(null)).toBe(0);
    });

    it('returns 0 for degenerate bboxes (zero width or height)', () => {
        expect(computeAspectRatio({ minX: 0, maxX: 0, minY: 0, maxY: 10 })).toBe(0);
        expect(computeAspectRatio({ minX: 0, maxX: 10, minY: 5, maxY: 5 })).toBe(0);
    });
});

describe('computeCompoundCardinalityFromCounts (M21)', () => {
    it('returns zeros for empty input', () => {
        const r = computeCompoundCardinalityFromCounts(new Map());
        expect(r).toEqual({
            largestGroupSize: 0,
            singletonFraction: 0,
            groupsCount: 0,
            sizeDistribution: {},
            groups: [],
        });
    });

    it('reports largest group across all parents', () => {
        const counts = new Map([['p1', 5], ['p2', 3], ['p3', 8]]);
        const r = computeCompoundCardinalityFromCounts(counts);
        expect(r.largestGroupSize).toBe(8);
    });

    it('singletonFraction counts parents with exactly 1 child', () => {
        const counts = new Map([['p1', 1], ['p2', 1], ['p3', 4], ['p4', 1]]);
        const r = computeCompoundCardinalityFromCounts(counts);
        expect(r.singletonFraction).toBe(0.75);
    });

    it('emits per-parent (parentId, size) tuples for overlay rendering', () => {
        const counts = new Map([['p1', 2], ['p2', 5]]);
        const r = computeCompoundCardinalityFromCounts(counts);
        expect(r.groups).toEqual([
            { parentId: 'p1', size: 2 },
            { parentId: 'p2', size: 5 },
        ]);
    });

    it('handles a single parent', () => {
        const r = computeCompoundCardinalityFromCounts(new Map([['solo', 7]]));
        expect(r).toEqual({
            largestGroupSize: 7,
            singletonFraction: 0,
            groupsCount: 1,
            sizeDistribution: { 7: 1 },
            groups: [{ parentId: 'solo', size: 7 }],
        });
    });

    it('emits a size→count distribution', () => {
        // 4 parents at sizes [3, 3, 5, 7] → dist {3: 2, 5: 1, 7: 1}
        const counts = new Map([
            ['p1', 3], ['p2', 3], ['p3', 5], ['p4', 7],
        ]);
        const r = computeCompoundCardinalityFromCounts(counts);
        expect(r.sizeDistribution).toEqual({ 3: 2, 5: 1, 7: 1 });
        expect(r.groupsCount).toBe(4);
    });

    it('groupsCount equals total compound parents (independent of size)', () => {
        const counts = new Map([['a', 1], ['b', 1], ['c', 1]]);
        const r = computeCompoundCardinalityFromCounts(counts);
        expect(r.groupsCount).toBe(3);
        expect(r.sizeDistribution).toEqual({ 1: 3 });
        expect(r.singletonFraction).toBe(1.0);
    });
});

describe('metricsToCSV', () => {
    const baseMetrics: DrawingMetrics = {
        nodes: 10,
        edges: 15,
        crossingsRaw: 3,
        crossingsNormalized: 0.95,
        crossingsPerEdge: 0.2,
        drawingArea: 12345.67,
        bboxWidth: 200,
        bboxHeight: 61.73,
        areaPerNode: 1234.567,
        edgeLengthCV: 0.42,
        edgeLengthMean: 100,
        edgeLengthStd: 42,
        uniqueCves: 7,
        aspectRatio: 0.5,
        compoundLargestGroupSize: 5,
        compoundSingletonFraction: 0.25,
        compoundGroupsCount: 4,
        compoundSizeDistribution: { 1: 1, 3: 2, 5: 1 },
        crossingsMeanAngleDeg: 67.5,
        crossingsMinAngleDeg: 30,
        crossingsRightAngleRatio: 0.5,
        crossingsTopPairShare: 0.6,
        crossingsTopPairLabel: 'HAS_VULN×LEADS_TO',
        crossingsTypePairDistribution: { 'HAS_VULN×LEADS_TO': 3, 'HAS_VULN×ENABLES': 2 },
        stressPerPair: 12.5,
        stressUnreachablePairs: 4,
        stressReachablePairs: 41,
        stressPerPairNormalizedEdge: 0.5,
        stressPerPairNormalizedDiagonal: 0.0125,
        stressPerPairNormalizedArea: 0.025,
        bridgeEdgeProportion: 0.2,
        meanContractionDepth: 1.5,
        bridgeEdgeCount: 3,
        bridgeChainLengthDistribution: { 1: 2, 2: 1 },
        meanEcrWeighted: 2.4,
        ecrCompoundsCount: 2,
        ecrPerCompound: [
            { parentId: 'p1', ecr: 3.0, childCount: 5 },
            { parentId: 'p2', ecr: 1.5, childCount: 5 },
        ],
        acrCvePrereqs: 0.68,
        acrCveOutcomes: 0.32,
        acrCveNodeCount: 87,
    };

    it('emits all columns with unique_cves and empty trivy_vuln_count when context missing', () => {
        const csv = metricsToCSV(baseMetrics);
        const lines = csv.trim().split('\n');
        expect(lines.length).toBe(2);
        expect(lines[0]).toBe('nodes,edges,unique_cves,trivy_vuln_count,crossings_raw,crossings_normalized,crossings_per_edge,drawing_area,bbox_width,bbox_height,area_per_node,edge_length_cv,edge_length_mean,edge_length_std,aspect_ratio,compound_groups_count,compound_largest_group_size,compound_singleton_fraction,crossings_mean_angle_deg,crossings_min_angle_deg,crossings_right_angle_ratio,crossings_top_pair_share,crossings_top_pair_label,stress_per_pair,stress_per_pair_normalized_edge,stress_per_pair_normalized_diagonal,stress_per_pair_normalized_area,stress_unreachable_pairs,stress_reachable_pairs,bridge_edge_proportion,mean_contraction_depth,bridge_edge_count,mean_ecr_weighted,ecr_compounds_count,acr_cve_prereqs,acr_cve_outcomes,acr_cve_node_count');
        expect(lines[1]).toBe('10,15,7,,3,0.9500,0.2000,12345.67,200.00,61.73,1234.57,0.4200,100.00,42.00,0.5000,4,5,0.2500,67.50,30.00,0.5000,0.6000,HAS_VULN×LEADS_TO,12.50,0.5000,0.0125,0.0250,4,41,0.2000,1.5000,3,2.4000,2,0.6800,0.3200,87');
    });

    it('populates trivy_vuln_count when provided via context', () => {
        const csv = metricsToCSV(baseMetrics, { trivyVulnCount: 189 });
        const lines = csv.trim().split('\n');
        expect(lines[1]).toBe('10,15,7,189,3,0.9500,0.2000,12345.67,200.00,61.73,1234.57,0.4200,100.00,42.00,0.5000,4,5,0.2500,67.50,30.00,0.5000,0.6000,HAS_VULN×LEADS_TO,12.50,0.5000,0.0125,0.0250,4,41,0.2000,1.5000,3,2.4000,2,0.6800,0.3200,87');
    });

    it('CSV-quotes a top-pair label that contains a comma or quote', () => {
        const csv = metricsToCSV({ ...baseMetrics, crossingsTopPairLabel: 'A,B' });
        // Stress columns are appended after the label; check for the embedded label
        expect(csv.trim().split('\n')[1]).toContain(',"A,B",');
        const csv2 = metricsToCSV({ ...baseMetrics, crossingsTopPairLabel: 'A"B' });
        expect(csv2.trim().split('\n')[1]).toContain(',"A""B",');
    });

    it('emits empty top-pair label as an empty field, not ""', () => {
        const csv = metricsToCSV({ ...baseMetrics, crossingsTopPairLabel: '' });
        // Two consecutive commas where the label sits, followed by stress columns
        expect(csv.trim().split('\n')[1]).toContain(',,12.50,');
    });
});

// =============================================================================
// JSON export — schema v1
// =============================================================================

describe('JSON metrics export (schema v1)', () => {
    const baseMetrics: DrawingMetrics = {
        nodes: 10,
        edges: 15,
        crossingsRaw: 3,
        crossingsNormalized: 0.95,
        crossingsPerEdge: 0.2,
        drawingArea: 12345.67,
        bboxWidth: 200,
        bboxHeight: 61.73,
        areaPerNode: 1234.567,
        edgeLengthCV: 0.42,
        edgeLengthMean: 100,
        edgeLengthStd: 42,
        uniqueCves: 7,
        aspectRatio: 0.5,
        compoundLargestGroupSize: 5,
        compoundSingletonFraction: 0.25,
        compoundGroupsCount: 4,
        compoundSizeDistribution: { 1: 1, 3: 2, 5: 1 },
        crossingsMeanAngleDeg: 67.5,
        crossingsMinAngleDeg: 30,
        crossingsRightAngleRatio: 0.5,
        crossingsTopPairShare: 0.6,
        crossingsTopPairLabel: 'HAS_VULN×LEADS_TO',
        crossingsTypePairDistribution: { 'HAS_VULN×LEADS_TO': 3, 'HAS_VULN×ENABLES': 2 },
        stressPerPair: 12.5,
        stressUnreachablePairs: 4,
        stressReachablePairs: 41,
        stressPerPairNormalizedEdge: 0.5,
        stressPerPairNormalizedDiagonal: 0.0125,
        stressPerPairNormalizedArea: 0.025,
        bridgeEdgeProportion: 0.2,
        meanContractionDepth: 1.5,
        bridgeEdgeCount: 3,
        bridgeChainLengthDistribution: { 1: 2, 2: 1 },
        meanEcrWeighted: 2.4,
        ecrCompoundsCount: 2,
        ecrPerCompound: [
            { parentId: 'p1', ecr: 3.0, childCount: 5 },
            { parentId: 'p2', ecr: 1.5, childCount: 5 },
        ],
        acrCvePrereqs: 0.68,
        acrCveOutcomes: 0.32,
        acrCveNodeCount: 87,
    };

    const baseSettings: SettingsSnapshot = {
        granularity: { HOST: 'ATTACKER', CPE: 'HOST', CVE: 'CPE', CWE: 'CVE', TI: 'CWE', VC: 'TI' },
        skip_layer_2: false,
        visibility_hidden: ['CWE', 'TI'],
        cve_merge_mode: 'outcomes',
        environment_filter: { ui: 'N', ac: 'L' },
        exploit_paths_only_active: false,
        force_refresh_on_last_rebuild: false,
        layout: 'dagre',
    };

    const baseDataSource: DataSourceSnapshot = {
        type: 'trivy',
        scans_uploaded_total: 1,
        scans_in_current_graph: [
            { id: 'scan-1', name: 'nginx:stable', vuln_count: 189, uploaded_at: '2026-05-04T10:00:00Z' },
        ],
        selection_was_implicit: true,
    };

    const fixedNow = new Date('2026-05-04T12:00:00.000Z');

    it('produces valid parseable JSON', () => {
        const json = metricsToJSON(baseMetrics, {}, baseSettings, baseDataSource, fixedNow);
        expect(() => JSON.parse(json)).not.toThrow();
    });

    it('schema_version is 1', () => {
        const snap = buildMetricsJsonSnapshot(baseMetrics, {}, baseSettings, baseDataSource, fixedNow);
        expect(snap.schema_version).toBe(1);
    });

    it('exported_at is ISO 8601', () => {
        const snap = buildMetricsJsonSnapshot(baseMetrics, {}, baseSettings, baseDataSource, fixedNow);
        expect(snap.exported_at).toBe('2026-05-04T12:00:00.000Z');
    });

    it('has app_version and git_sha', () => {
        const snap = buildMetricsJsonSnapshot(baseMetrics, {}, baseSettings, baseDataSource, fixedNow);
        expect(typeof snap.app_version).toBe('string');
        expect(snap.app_version.length).toBeGreaterThan(0);
        expect(typeof snap.git_sha).toBe('string');
        expect(snap.git_sha.length).toBeGreaterThan(0);
    });

    it('all DrawingMetrics fields appear under metrics key with correct names', () => {
        const obj = metricsToJsonObject(baseMetrics, { trivyVulnCount: 189 });
        expect(obj).toEqual({
            nodes: 10,
            edges: 15,
            unique_cves: 7,
            trivy_vuln_count: 189,
            crossings_raw: 3,
            crossings_normalized: 0.95,
            crossings_per_edge: 0.2,
            drawing_area: 12345.67,
            bbox_width: 200,
            bbox_height: 61.73,
            area_per_node: 1234.567,
            edge_length_cv: 0.42,
            edge_length_mean: 100,
            edge_length_std: 42,
            aspect_ratio: 0.5,
            compound_groups_count: 4,
            compound_largest_group_size: 5,
            compound_singleton_fraction: 0.25,
            compound_size_distribution: { 1: 1, 3: 2, 5: 1 },
            crossings_mean_angle_deg: 67.5,
            crossings_min_angle_deg: 30,
            crossings_right_angle_ratio: 0.5,
            crossings_top_pair_share: 0.6,
            crossings_top_pair_label: 'HAS_VULN×LEADS_TO',
            crossings_type_pair_distribution: { 'HAS_VULN×LEADS_TO': 3, 'HAS_VULN×ENABLES': 2 },
            stress_per_pair: 12.5,
            stress_per_pair_normalized_edge: 0.5,
            stress_per_pair_normalized_diagonal: 0.0125,
            stress_per_pair_normalized_area: 0.025,
            stress_unreachable_pairs: 4,
            stress_reachable_pairs: 41,
            bridge_edge_proportion: 0.2,
            mean_contraction_depth: 1.5,
            bridge_edge_count: 3,
            bridge_chain_length_distribution: { 1: 2, 2: 1 },
            mean_ecr_weighted: 2.4,
            ecr_compounds_count: 2,
            ecr_per_compound: [
                { parentId: 'p1', ecr: 3.0, childCount: 5 },
                { parentId: 'p2', ecr: 1.5, childCount: 5 },
            ],
            acr_cve_prereqs: 0.68,
            acr_cve_outcomes: 0.32,
            acr_cve_node_count: 87,
        });
    });

    it('trivy_vuln_count is null when context omits it (vs CSV empty string)', () => {
        const obj = metricsToJsonObject(baseMetrics);
        expect(obj.trivy_vuln_count).toBeNull();
    });

    it('settings snapshot is included verbatim', () => {
        const snap = buildMetricsJsonSnapshot(baseMetrics, {}, baseSettings, baseDataSource, fixedNow);
        expect(snap.settings).toEqual(baseSettings);
    });

    it('data_source includes the scan list', () => {
        const snap = buildMetricsJsonSnapshot(baseMetrics, {}, baseSettings, baseDataSource, fixedNow);
        expect(snap.data_source.type).toBe('trivy');
        expect(snap.data_source.scans_uploaded_total).toBe(1);
        expect(snap.data_source.scans_in_current_graph).toHaveLength(1);
    });

    it('regression: keys present in v1 are stable (top-level + metrics)', () => {
        // Adding a new metric should NOT remove these — protects forward-compat consumers.
        const snap = buildMetricsJsonSnapshot(baseMetrics, {}, baseSettings, baseDataSource, fixedNow);
        const topLevel = Object.keys(snap).sort();
        expect(topLevel).toEqual([
            'app_version',
            'data_source',
            'exported_at',
            'git_sha',
            'metrics',
            'schema_version',
            'settings',
        ]);

        const metricKeys = Object.keys(snap.metrics).sort();
        expect(metricKeys).toEqual([
            'acr_cve_node_count',
            'acr_cve_outcomes',
            'acr_cve_prereqs',
            'area_per_node',
            'aspect_ratio',
            'bbox_height',
            'bbox_width',
            'bridge_chain_length_distribution',
            'bridge_edge_count',
            'bridge_edge_proportion',
            'compound_groups_count',
            'compound_largest_group_size',
            'compound_singleton_fraction',
            'compound_size_distribution',
            'crossings_mean_angle_deg',
            'crossings_min_angle_deg',
            'crossings_normalized',
            'crossings_per_edge',
            'crossings_raw',
            'crossings_right_angle_ratio',
            'crossings_top_pair_label',
            'crossings_top_pair_share',
            'crossings_type_pair_distribution',
            'drawing_area',
            'ecr_compounds_count',
            'ecr_per_compound',
            'edge_length_cv',
            'edge_length_mean',
            'edge_length_std',
            'edges',
            'mean_contraction_depth',
            'mean_ecr_weighted',
            'nodes',
            'stress_per_pair',
            'stress_per_pair_normalized_area',
            'stress_per_pair_normalized_diagonal',
            'stress_per_pair_normalized_edge',
            'stress_reachable_pairs',
            'stress_unreachable_pairs',
            'trivy_vuln_count',
            'unique_cves',
        ]);
    });

    it('JSON output ends with a newline (POSIX-friendly)', () => {
        const json = metricsToJSON(baseMetrics, {}, baseSettings, baseDataSource, fixedNow);
        expect(json.endsWith('\n')).toBe(true);
    });
});

describe('buildDataSourceSnapshot', () => {
    const scans = [
        { id: 'a', name: 'nginx', filename: 'a.json', uploaded_at: 't', vuln_count: 5 },
        { id: 'b', name: 'redis', filename: 'b.json', uploaded_at: 't', vuln_count: 12 },
    ];

    it('returns mock-source for empty scan list', () => {
        const ds = buildDataSourceSnapshot([]);
        expect(ds.type).toBe('mock');
        expect(ds.scans_uploaded_total).toBe(0);
        expect(ds.scans_in_current_graph).toEqual([]);
        expect(ds.selection_was_implicit).toBe(true);
    });

    it('returns trivy-source with all scans when no selection is given (implicit)', () => {
        const ds = buildDataSourceSnapshot(scans);
        expect(ds.type).toBe('trivy');
        expect(ds.scans_uploaded_total).toBe(2);
        expect(ds.selection_was_implicit).toBe(true);
        expect(ds.scans_in_current_graph).toEqual([
            { id: 'a', name: 'nginx', vuln_count: 5, uploaded_at: 't' },
            { id: 'b', name: 'redis', vuln_count: 12, uploaded_at: 't' },
        ]);
    });

    it('treats undefined / null / [] selection as implicit (lists all uploaded)', () => {
        expect(buildDataSourceSnapshot(scans, undefined).selection_was_implicit).toBe(true);
        expect(buildDataSourceSnapshot(scans, null).selection_was_implicit).toBe(true);
        expect(buildDataSourceSnapshot(scans, []).selection_was_implicit).toBe(true);
        expect(buildDataSourceSnapshot(scans, []).scans_in_current_graph).toHaveLength(2);
    });

    it('filters scans_in_current_graph when an explicit selection is given', () => {
        const ds = buildDataSourceSnapshot(scans, ['a']);
        expect(ds.scans_uploaded_total).toBe(2);            // total still reflects uploads
        expect(ds.scans_in_current_graph).toHaveLength(1);  // but only "a" is in the graph
        expect(ds.scans_in_current_graph[0].id).toBe('a');
        expect(ds.selection_was_implicit).toBe(false);
    });

    it('handles selection of unknown ids gracefully (filters to empty)', () => {
        const ds = buildDataSourceSnapshot(scans, ['nonexistent']);
        expect(ds.scans_in_current_graph).toEqual([]);
        expect(ds.selection_was_implicit).toBe(false);
    });
});
