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
    metricsToCSV,
    metricsToJSON,
    metricsToJsonObject,
    buildMetricsJsonSnapshot,
    buildDataSourceSnapshot,
    type DrawingMetrics,
    type DataSourceSnapshot,
} from './metrics';
import type { SettingsSnapshot } from './settingsSnapshot';

// Helper to build edge records for testing
function mkEdge(sId: string, tId: string, sx: number, sy: number, tx: number, ty: number) {
    return {
        source: { x: sx, y: sy },
        target: { x: tx, y: ty },
        sourceId: sId,
        targetId: tId
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
        areaPerNode: 1234.567,
        edgeLengthCV: 0.42,
        uniqueCves: 7,
        aspectRatio: 0.5,
        compoundLargestGroupSize: 5,
        compoundSingletonFraction: 0.25,
        compoundGroupsCount: 4,
        compoundSizeDistribution: { 1: 1, 3: 2, 5: 1 },
    };

    it('emits all columns with unique_cves and empty trivy_vuln_count when context missing', () => {
        const csv = metricsToCSV(baseMetrics);
        const lines = csv.trim().split('\n');
        expect(lines.length).toBe(2);
        expect(lines[0]).toBe('nodes,edges,unique_cves,trivy_vuln_count,crossings_raw,crossings_normalized,crossings_per_edge,drawing_area,area_per_node,edge_length_cv,aspect_ratio,compound_groups_count,compound_largest_group_size,compound_singleton_fraction');
        expect(lines[1]).toBe('10,15,7,,3,0.9500,0.2000,12345.67,1234.57,0.4200,0.5000,4,5,0.2500');
    });

    it('populates trivy_vuln_count when provided via context', () => {
        const csv = metricsToCSV(baseMetrics, { trivyVulnCount: 189 });
        const lines = csv.trim().split('\n');
        expect(lines[1]).toBe('10,15,7,189,3,0.9500,0.2000,12345.67,1234.57,0.4200,0.5000,4,5,0.2500');
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
        areaPerNode: 1234.567,
        edgeLengthCV: 0.42,
        uniqueCves: 7,
        aspectRatio: 0.5,
        compoundLargestGroupSize: 5,
        compoundSingletonFraction: 0.25,
        compoundGroupsCount: 4,
        compoundSizeDistribution: { 1: 1, 3: 2, 5: 1 },
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
            { id: 'scan-1', name: 'nginx:stable', vuln_count: 189 },
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
            area_per_node: 1234.567,
            edge_length_cv: 0.42,
            aspect_ratio: 0.5,
            compound_groups_count: 4,
            compound_largest_group_size: 5,
            compound_singleton_fraction: 0.25,
            compound_size_distribution: { 1: 1, 3: 2, 5: 1 },
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
            'area_per_node',
            'aspect_ratio',
            'compound_groups_count',
            'compound_largest_group_size',
            'compound_singleton_fraction',
            'compound_size_distribution',
            'crossings_normalized',
            'crossings_per_edge',
            'crossings_raw',
            'drawing_area',
            'edge_length_cv',
            'edges',
            'nodes',
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
            { id: 'a', name: 'nginx', vuln_count: 5 },
            { id: 'b', name: 'redis', vuln_count: 12 },
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
