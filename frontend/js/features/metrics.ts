/**
 * Graph drawing quality metrics per Purchase (2002),
 * "Metrics for Graph Drawing Aesthetics."
 *
 * Implements three metrics on the currently visible graph:
 *   1. Edge crossings (raw count + normalized [0,1], higher = fewer crossings)
 *   2. Drawing area (bounding box in logical units, center-point method)
 *   3. Edge length coefficient of variation (std / mean, lower = more uniform)
 *
 * All computations use logical coordinates from cy.position(), so metrics
 * are invariant under zoom and pan.
 */

import { getCy } from '../graph/core';

export interface DrawingMetrics {
    nodes: number;
    edges: number;
    crossingsRaw: number;
    crossingsNormalized: number;  // [0, 1], 1 = no crossings (Purchase 2002)
    crossingsPerEdge: number;      // raw crossings / |E|, 0 if |E| = 0
    drawingArea: number;           // logical units squared, center-point method
    edgeLengthCV: number;          // std / mean, 0 if undefined
}

export interface Point {
    x: number;
    y: number;
}

export interface EdgeEndpoints {
    source: Point;
    target: Point;
    sourceId: string;
    targetId: string;
}

export interface CrossingInfo {
    point: Point;
    edgeA: EdgeEndpoints;
    edgeB: EdgeEndpoints;
}

/**
 * Extract edge endpoints from the currently visible Cytoscape graph.
 * Exposed so debug overlays can use the same filter the metrics see.
 */
export function getVisibleNodePoints(): Point[] {
    const cy = getCy();
    if (!cy) return [];
    const points: Point[] = [];
    cy.nodes(':visible').forEach(n => {
        if (n.data('type') === 'CROSSING_DEBUG') return;
        if (n.data('type') === 'AREA_DEBUG') return;
        if (n.data('type') === 'UNIT_EDGE_NODE') return;
        const p = n.position();
        points.push({ x: p.x, y: p.y });
    });
    return points;
}

export function getVisibleEdgeEndpoints(): EdgeEndpoints[] {
    const cy = getCy();
    if (!cy) return [];

    const edges: EdgeEndpoints[] = [];
    cy.edges(':visible').forEach(e => {
        const src = e.source();
        const tgt = e.target();
        if (!src || !tgt) return;
        // Ignore edges touching debug overlay nodes
        const srcType = src.data('type');
        const tgtType = tgt.data('type');
        if (
            srcType === 'CROSSING_DEBUG' || tgtType === 'CROSSING_DEBUG' ||
            srcType === 'AREA_DEBUG' || tgtType === 'AREA_DEBUG' ||
            srcType === 'UNIT_EDGE_NODE' || tgtType === 'UNIT_EDGE_NODE'
        ) {
            return;
        }
        const sPos = src.position();
        const tPos = tgt.position();
        edges.push({
            source: { x: sPos.x, y: sPos.y },
            target: { x: tPos.x, y: tPos.y },
            sourceId: src.id(),
            targetId: tgt.id()
        });
    });
    return edges;
}

/**
 * Compute drawing quality metrics on the currently visible graph.
 * "Visible" = Cytoscape selector :visible, which excludes nodes/edges with
 * display: none (e.g. exploit-hidden, merge-hidden CVEs).
 *
 * Compound parents (ATTACKER_BOX, CVE_GROUP) are included; their parent-child
 * relationships are not edges, so they do not affect crossings or edge length.
 * Their center position equals their children's centroid, so they do not
 * meaningfully affect the bounding box either.
 */
export function computeMetrics(): DrawingMetrics | null {
    const cy = getCy();
    if (!cy) return null;

    const visibleNodes = cy.nodes(':visible').filter(n => {
        const t = n.data('type');
        return t !== 'CROSSING_DEBUG' && t !== 'AREA_DEBUG' && t !== 'UNIT_EDGE_NODE';
    });
    const visibleEdges = cy.edges(':visible');

    const nodeCount = visibleNodes.length;
    const edgeCount = visibleEdges.length;

    // Extract node positions
    const points: Point[] = [];
    visibleNodes.forEach(n => {
        const p = n.position();
        points.push({ x: p.x, y: p.y });
    });

    // Extract edge endpoints (skips edges whose endpoints are not visible)
    const edges = getVisibleEdgeEndpoints();

    // 1. Edge crossings
    const crossingsRaw = countCrossings(edges);
    const crossingsNormalized = normalizeCrossings(crossingsRaw, edges);
    const crossingsPerEdge = edges.length > 0 ? crossingsRaw / edges.length : 0;

    // 2. Drawing area (center-point bounding box)
    const drawingArea = computeDrawingArea(points);

    // 3. Edge length CV
    const edgeLengthCV = computeEdgeLengthCV(edges);

    return {
        nodes: nodeCount,
        edges: edgeCount,
        crossingsRaw,
        crossingsNormalized,
        crossingsPerEdge,
        drawingArea,
        edgeLengthCV
    };
}

/**
 * Find all counted crossings, returning each intersection point together
 * with the two edges that cross. Edge pairs sharing an endpoint are skipped.
 *
 * Complexity: O(|E|^2).
 */
export function findCrossings(edges: EdgeEndpoints[]): CrossingInfo[] {
    const result: CrossingInfo[] = [];
    for (let i = 0; i < edges.length; i++) {
        const a = edges[i];
        for (let j = i + 1; j < edges.length; j++) {
            const b = edges[j];
            // Skip pairs sharing an endpoint
            if (
                a.sourceId === b.sourceId ||
                a.sourceId === b.targetId ||
                a.targetId === b.sourceId ||
                a.targetId === b.targetId
            ) {
                continue;
            }
            const point = segmentIntersectionPoint(a.source, a.target, b.source, b.target);
            if (point !== null) {
                result.push({ point, edgeA: a, edgeB: b });
            }
        }
    }
    return result;
}

/**
 * Count the number of pairs of edges whose line segments intersect.
 * Convenience wrapper around findCrossings.
 */
export function countCrossings(edges: EdgeEndpoints[]): number {
    return findCrossings(edges).length;
}

/**
 * Return the strict-interior intersection point of two segments, or null
 * if they do not cross in their interiors.
 */
export function segmentIntersectionPoint(
    p1: Point, p2: Point, p3: Point, p4: Point
): Point | null {
    const denom = (p1.x - p2.x) * (p3.y - p4.y) - (p1.y - p2.y) * (p3.x - p4.x);
    if (denom === 0) return null; // parallel or collinear

    const tNum = (p1.x - p3.x) * (p3.y - p4.y) - (p1.y - p3.y) * (p3.x - p4.x);
    const uNum = -((p1.x - p2.x) * (p1.y - p3.y) - (p1.y - p2.y) * (p1.x - p3.x));

    const t = tNum / denom;
    const u = uNum / denom;

    // Strict interior (exclude endpoint touches)
    if (t <= 0 || t >= 1 || u <= 0 || u >= 1) return null;

    return {
        x: p1.x + t * (p2.x - p1.x),
        y: p1.y + t * (p2.y - p1.y)
    };
}

/**
 * Test whether two line segments (p1→p2) and (p3→p4) intersect in their interiors.
 * Uses cross-product sign test. Does not treat collinear overlap as a crossing
 * (consistent with Purchase 2002's definition).
 */
export function segmentsIntersect(p1: Point, p2: Point, p3: Point, p4: Point): boolean {
    const d1 = direction(p3, p4, p1);
    const d2 = direction(p3, p4, p2);
    const d3 = direction(p1, p2, p3);
    const d4 = direction(p1, p2, p4);

    if (
        ((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) &&
        ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0))
    ) {
        return true;
    }
    return false;
}

function direction(i: Point, j: Point, k: Point): number {
    return (k.x - i.x) * (j.y - i.y) - (j.x - i.x) * (k.y - i.y);
}

/**
 * Normalize crossings per Purchase (2002):
 *   score = 1 - (crossings / max_possible)
 * where max_possible = C(|E|,2) - sum over nodes of C(deg(v), 2)
 * (subtracting pairs that share a node, which cannot cross).
 *
 * Returns 1.0 when there are 0 crossings, 0.0 when max_possible crossings occur.
 * Returns 1.0 (best) when max_possible is 0 (i.e. fewer than 2 non-adjacent edge pairs).
 */
export function normalizeCrossings(crossings: number, edges: EdgeEndpoints[]): number {
    const m = edges.length;
    if (m < 2) return 1.0;

    // degree count per node
    const degree: Record<string, number> = {};
    for (const e of edges) {
        degree[e.sourceId] = (degree[e.sourceId] || 0) + 1;
        degree[e.targetId] = (degree[e.targetId] || 0) + 1;
    }

    let adjacentPairs = 0;
    for (const id in degree) {
        const d = degree[id];
        adjacentPairs += (d * (d - 1)) / 2;
    }

    const totalPairs = (m * (m - 1)) / 2;
    const maxCrossings = totalPairs - adjacentPairs;

    if (maxCrossings <= 0) return 1.0;
    return 1.0 - crossings / maxCrossings;
}

/**
 * Drawing area via center-point method: bounding box of node positions
 * (ignoring node dimensions). Returns logical units squared.
 * Single node or empty graph returns 0.
 */
export function computeDrawingArea(points: Point[]): number {
    const bb = computeBoundingBox(points);
    if (!bb) return 0;
    return (bb.maxX - bb.minX) * (bb.maxY - bb.minY);
}

/**
 * Compute axis-aligned bounding box over a set of points.
 * Returns null if fewer than one point.
 */
export function computeBoundingBox(points: Point[]): { minX: number; maxX: number; minY: number; maxY: number } | null {
    if (points.length < 1) return null;
    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;
    for (const p of points) {
        if (p.x < minX) minX = p.x;
        if (p.x > maxX) maxX = p.x;
        if (p.y < minY) minY = p.y;
        if (p.y > maxY) maxY = p.y;
    }
    return { minX, maxX, minY, maxY };
}

/**
 * Euclidean length of each edge in logical units.
 */
export function edgeLengths(edges: EdgeEndpoints[]): number[] {
    return edges.map(e => {
        const dx = e.source.x - e.target.x;
        const dy = e.source.y - e.target.y;
        return Math.sqrt(dx * dx + dy * dy);
    });
}

/**
 * Mean edge length in logical units.
 */
export function computeMeanEdgeLength(edges: EdgeEndpoints[]): number {
    if (edges.length < 1) return 0;
    const lengths = edgeLengths(edges);
    return lengths.reduce((a, b) => a + b, 0) / lengths.length;
}

/**
 * Population standard deviation of edge lengths (same units as edges).
 */
export function computeEdgeLengthStd(edges: EdgeEndpoints[]): number {
    if (edges.length < 1) return 0;
    const lengths = edgeLengths(edges);
    const mean = lengths.reduce((a, b) => a + b, 0) / lengths.length;
    const variance = lengths.reduce((s, l) => s + (l - mean) ** 2, 0) / lengths.length;
    return Math.sqrt(variance);
}

/**
 * Edge length coefficient of variation: std(lengths) / mean(lengths).
 * Uses population standard deviation (dividing by N, not N-1) to match
 * Purchase (2002).
 * Returns 0 when there are fewer than 2 edges or when the mean is 0.
 */
export function computeEdgeLengthCV(edges: EdgeEndpoints[]): number {
    if (edges.length < 1) return 0;

    const lengths = edges.map(e => {
        const dx = e.source.x - e.target.x;
        const dy = e.source.y - e.target.y;
        return Math.sqrt(dx * dx + dy * dy);
    });

    const mean = lengths.reduce((a, b) => a + b, 0) / lengths.length;
    if (mean === 0) return 0;

    const variance = lengths.reduce((s, l) => s + (l - mean) ** 2, 0) / lengths.length;
    const std = Math.sqrt(variance);

    return std / mean;
}

/**
 * Produce a CSV representation of the metrics (header row + single data row).
 */
export function metricsToCSV(m: DrawingMetrics): string {
    const header = 'nodes,edges,crossings_raw,crossings_normalized,crossings_per_edge,drawing_area,edge_length_cv';
    const row = [
        m.nodes,
        m.edges,
        m.crossingsRaw,
        m.crossingsNormalized.toFixed(4),
        m.crossingsPerEdge.toFixed(4),
        m.drawingArea.toFixed(2),
        m.edgeLengthCV.toFixed(4)
    ].join(',');
    return header + '\n' + row + '\n';
}

/**
 * Trigger a CSV download in the browser.
 */
export function downloadMetricsCSV(m: DrawingMetrics): void {
    const csv = metricsToCSV(m);
    const timestamp = formatTimestamp(new Date());
    const filename = `pagdrawer-metrics-${timestamp}.csv`;

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

function formatTimestamp(d: Date): string {
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}-${pad(d.getHours())}-${pad(d.getMinutes())}`;
}
