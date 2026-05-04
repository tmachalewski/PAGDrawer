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
    };

    it('emits all columns with unique_cves and empty trivy_vuln_count when context missing', () => {
        const csv = metricsToCSV(baseMetrics);
        const lines = csv.trim().split('\n');
        expect(lines.length).toBe(2);
        expect(lines[0]).toBe('nodes,edges,unique_cves,trivy_vuln_count,crossings_raw,crossings_normalized,crossings_per_edge,drawing_area,area_per_node,edge_length_cv');
        expect(lines[1]).toBe('10,15,7,,3,0.9500,0.2000,12345.67,1234.57,0.4200');
    });

    it('populates trivy_vuln_count when provided via context', () => {
        const csv = metricsToCSV(baseMetrics, { trivyVulnCount: 189 });
        const lines = csv.trim().split('\n');
        expect(lines[1]).toBe('10,15,7,189,3,0.9500,0.2000,12345.67,1234.57,0.4200');
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
    };

    const baseSettings: SettingsSnapshot = {
        granularity: { HOST: 'ATTACKER', CPE: 'HOST', CVE: 'CPE', CWE: 'CVE', TI: 'CWE', VC: 'TI' },
        skip_layer_2: false,
        visibility_hidden: ['CWE', 'TI'],
        cve_merge_mode: 'outcomes',
        environment_filter: { ui: 'N', ac: 'L' },
        exploit_paths_active: false,
        force_refresh_on_last_rebuild: false,
        layout: 'dagre',
    };

    const baseDataSource: DataSourceSnapshot = {
        type: 'trivy',
        scans_uploaded_total: 1,
        scans_in_current_graph: [
            { id: 'scan-1', name: 'nginx:stable', vuln_count: 189 },
        ],
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
    it('returns mock-source for empty scan list', () => {
        const ds = buildDataSourceSnapshot([]);
        expect(ds.type).toBe('mock');
        expect(ds.scans_uploaded_total).toBe(0);
        expect(ds.scans_in_current_graph).toEqual([]);
    });

    it('returns trivy-source with mapped scan refs when scans exist', () => {
        const ds = buildDataSourceSnapshot([
            { id: 'a', name: 'nginx', filename: 'a.json', uploaded_at: 't', vuln_count: 5 },
            { id: 'b', name: 'redis', filename: 'b.json', uploaded_at: 't', vuln_count: 12 },
        ]);
        expect(ds.type).toBe('trivy');
        expect(ds.scans_uploaded_total).toBe(2);
        expect(ds.scans_in_current_graph).toEqual([
            { id: 'a', name: 'nginx', vuln_count: 5 },
            { id: 'b', name: 'redis', vuln_count: 12 },
        ]);
    });
});
