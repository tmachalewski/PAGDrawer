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
import { getGitSha, getAppVersion } from '../config/buildInfo';
import type { SettingsSnapshot } from './settingsSnapshot';
import type { ScanInfo } from '../types';

export interface DrawingMetrics {
    nodes: number;
    edges: number;
    crossingsRaw: number;
    crossingsNormalized: number;  // [0, 1], 1 = no crossings (Purchase 2002)
    crossingsPerEdge: number;      // raw crossings / |E|, 0 if |E| = 0
    drawingArea: number;           // logical units squared, center-point method
    areaPerNode: number;           // drawing area / |V|, 0 if |V| = 0
    edgeLengthCV: number;          // std / mean, 0 if undefined
    uniqueCves: number;            // distinct base CVE IDs in the live graph (:dN/@... stripped)
    aspectRatio: number;           // M9: min(w,h)/max(w,h) of bbox, [0, 1] (1 = square)
    compoundLargestGroupSize: number; // M21: max children among compound parents
    compoundSingletonFraction: number; // M21: fraction of compound parents with exactly 1 child
    compoundGroupsCount: number;    // M21: total number of compound parents
    /**
     * M21: full size → count distribution. Keys are member counts (e.g. 2, 3, 4),
     * values are the number of compound parents with that exact size. Empty map
     * when no compound parents exist. Lives in JSON export and modal histogram;
     * not flattened into CSV (variable column set would break diffs).
     */
    compoundSizeDistribution: Record<number, number>;

    // M2 — Crossing angle metrics. Reported in degrees for human readability.
    crossingsMeanAngleDeg: number;     // mean across all crossings, 0 when no crossings
    crossingsMinAngleDeg: number;      // worst (most acute) angle, 0 when no crossings
    crossingsRightAngleRatio: number;  // share within ±15° of 90°, 0 when no crossings

    // M25 — Type-pair crossing decomposition.
    crossingsTopPairShare: number;     // largest type-pair's fraction of all crossings
    crossingsTopPairLabel: string;     // e.g. "HAS_VULN×LEADS_TO" or "" when no crossings
    /**
     * M25: full type-pair → count distribution. Keys are "typeA×typeB" strings
     * with the pair sorted lexicographically. JSON-only (variable cardinality
     * would break stable CSV headers).
     */
    crossingsTypePairDistribution: Record<string, number>;

    // M1 — Stress (Purchase 2002 / Kamada-Kawai-style).
    stressPerPair: number;             // mean (‖p_i − p_j‖_layout − d_ij)² over reachable pairs
    stressUnreachablePairs: number;    // unordered i<j pair count where d_ij is undefined
    stressReachablePairs: number;      // denominator for stressPerPair (useful for weighting)
    /**
     * Stress with layout distance scaled by the mean edge length
     * (Kamada-Kawai convention). Dimensionless; comparable across graphs.
     */
    stressPerPairNormalizedEdge: number;
    /**
     * Stress with layout distance scaled by the bbox diagonal
     * (sqrt(w² + h²)). Dimensionless; comparable across drawings of
     * different sizes.
     */
    stressPerPairNormalizedDiagonal: number;
    /**
     * Stress with layout distance scaled by the square root of the
     * drawing area (sqrt(w · h) — geometric mean of bbox dimensions).
     * Dimensionless.
     */
    stressPerPairNormalizedArea: number;
}

export interface CompoundCardinality {
    largestGroupSize: number;
    singletonFraction: number;
    groupsCount: number;
    /** size → count map for the histogram. */
    sizeDistribution: Record<number, number>;
    /** Per-parent member counts, useful for the overlay's per-parent badges. */
    groups: Array<{ parentId: string; size: number }>;
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
    /**
     * Edge `data('type')` from Cytoscape (e.g. 'HAS_VULN', 'IS_INSTANCE_OF').
     * Empty string when the edge has no type set. Carried so M25
     * (type-pair decomposition) and the overlay can categorise crossings.
     */
    type: string;
}

/**
 * A visible node with its id and logical position. Used by metrics that
 * need to correlate graph topology (via id) with layout geometry (via
 * position) — currently M1 Stress, future M11/M12.
 */
export interface NodeWithPosition {
    id: string;
    x: number;
    y: number;
}

export interface CrossingInfo {
    point: Point;
    edgeA: EdgeEndpoints;
    edgeB: EdgeEndpoints;
    /** M2 — acute angle between the crossing edges, radians in [0, π/2]. */
    angle: number;
    /** M25 — pair of edge types involved in this crossing, sorted lex. */
    edgeAType: string;
    edgeBType: string;
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

/**
 * Visible non-debug nodes, paired with their ids. Used by topology-
 * preservation metrics (M1 Stress, future M11/M12) which need to look up
 * graph distance by id while reading layout distance from (x, y).
 */
export function getVisibleNodesWithIds(): NodeWithPosition[] {
    const cy = getCy();
    if (!cy) return [];
    const nodes: NodeWithPosition[] = [];
    cy.nodes(':visible').forEach(n => {
        const t = n.data('type');
        if (t === 'CROSSING_DEBUG' || t === 'AREA_DEBUG' || t === 'UNIT_EDGE_NODE') return;
        const p = n.position();
        nodes.push({ id: n.id(), x: p.x, y: p.y });
    });
    return nodes;
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
        const edgeType = e.data('type');
        edges.push({
            source: { x: sPos.x, y: sPos.y },
            target: { x: tPos.x, y: tPos.y },
            sourceId: src.id(),
            targetId: tgt.id(),
            type: typeof edgeType === 'string' ? edgeType : '',
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

    // 1. Edge crossings — compute once, then derive raw / normalised /
    //    M2 angle stats / M25 type-pair stats from the same CrossingInfo list.
    const crossingInfos = findCrossings(edges);
    const crossingsRaw = crossingInfos.length;
    const crossingsNormalized = normalizeCrossings(crossingsRaw, edges);
    const crossingsPerEdge = edges.length > 0 ? crossingsRaw / edges.length : 0;
    const angleStats = computeCrossingAngleStats(crossingInfos);
    const typePairStats = computeTypePairCrossingStats(crossingInfos);
    const RAD_TO_DEG = 180 / Math.PI;

    // 2. Drawing area (center-point bounding box) + M9 aspect ratio
    const bbox = computeBoundingBox(points);
    const drawingArea = computeDrawingArea(points);
    const areaPerNode = nodeCount > 0 ? drawingArea / nodeCount : 0;
    const aspectRatio = computeAspectRatio(bbox);

    // 3. Edge length CV
    const edgeLengthCV = computeEdgeLengthCV(edges);

    // 5. M21 — compound-parent cardinality (largest group + singleton fraction)
    const compound = computeCompoundCardinality();

    // 6. M1 — Stress (Purchase 2002). Reuses the same visible-edge list and
    // a fresh BFS-APSP. The APSP matrix is also the prerequisite for
    // M11/M12 (Stage 7) — a future cache will share it across metrics.
    const stress = computeStress();

    // 4. Unique CVE count — strip :dN depth and @... context suffixes
    const uniqueCveBases = new Set<string>();
    visibleNodes.forEach(n => {
        if (n.data('type') === 'CVE') {
            const id = n.id();
            uniqueCveBases.add(id.replace(/[:@].*$/, ''));
        }
    });
    const uniqueCves = uniqueCveBases.size;

    return {
        nodes: nodeCount,
        edges: edgeCount,
        crossingsRaw,
        crossingsNormalized,
        crossingsPerEdge,
        drawingArea,
        areaPerNode,
        edgeLengthCV,
        uniqueCves,
        aspectRatio,
        compoundLargestGroupSize: compound.largestGroupSize,
        compoundSingletonFraction: compound.singletonFraction,
        compoundGroupsCount: compound.groupsCount,
        compoundSizeDistribution: compound.sizeDistribution,
        crossingsMeanAngleDeg: angleStats.meanRad * RAD_TO_DEG,
        crossingsMinAngleDeg: angleStats.minRad * RAD_TO_DEG,
        crossingsRightAngleRatio: angleStats.rightAngleRatio,
        crossingsTopPairShare: typePairStats.topPairShare,
        crossingsTopPairLabel: typePairStats.topPairLabel,
        crossingsTypePairDistribution: typePairStats.distribution,
        stressPerPair: stress.raw,
        stressUnreachablePairs: stress.unreachablePairs,
        stressReachablePairs: stress.reachablePairs,
        stressPerPairNormalizedEdge: stress.normalizedEdge,
        stressPerPairNormalizedDiagonal: stress.normalizedDiagonal,
        stressPerPairNormalizedArea: stress.normalizedArea,
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
                const angle = computeCrossingAngle(a, b);
                // Sort the type pair lexicographically so {(t1, t2), (t2, t1)}
                // collapse to one bucket in the M25 distribution.
                const [edgeAType, edgeBType] = a.type <= b.type
                    ? [a.type, b.type]
                    : [b.type, a.type];
                result.push({ point, edgeA: a, edgeB: b, angle, edgeAType, edgeBType });
            }
        }
    }
    return result;
}

/**
 * M2 — acute angle between two crossing edges, in radians ∈ [0, π/2].
 *
 * Uses `arctan2(|cross|, |dot|)` of edge direction vectors per Huang, Eades
 * and Hong 2014. Absolute values fold the result into the acute range
 * regardless of edge orientation (source→target vs target→source produce
 * the same angle).
 *
 * Returns 0 when either edge is degenerate (zero-length).
 */
export function computeCrossingAngle(a: EdgeEndpoints, b: EdgeEndpoints): number {
    const ax = a.target.x - a.source.x;
    const ay = a.target.y - a.source.y;
    const bx = b.target.x - b.source.x;
    const by = b.target.y - b.source.y;
    const cross = Math.abs(ax * by - ay * bx);
    const dot = Math.abs(ax * bx + ay * by);
    if (cross === 0 && dot === 0) return 0; // degenerate
    return Math.atan2(cross, dot); // in [0, π/2]
}

/**
 * Count the number of pairs of edges whose line segments intersect.
 * Convenience wrapper around findCrossings.
 */
export function countCrossings(edges: EdgeEndpoints[]): number {
    return findCrossings(edges).length;
}

/**
 * M2 — aggregate crossing-angle scalars from a CrossingInfo[] (all in radians).
 *
 * @param rightAngleToleranceRad Tolerance window around π/2. Default 15° per
 *                               Huang, Eades and Hong 2014.
 *
 * Returns angles in **radians**; a UI helper converts to degrees for display.
 * Empty input → all zeros (the modal renders this as "—" via the table layer).
 */
export function computeCrossingAngleStats(
    crossings: CrossingInfo[],
    rightAngleToleranceRad: number = Math.PI / 12,
): { meanRad: number; minRad: number; rightAngleRatio: number } {
    if (crossings.length === 0) {
        return { meanRad: 0, minRad: 0, rightAngleRatio: 0 };
    }
    let sum = 0;
    let min = Infinity;
    let nearRight = 0;
    const target = Math.PI / 2;
    for (const c of crossings) {
        sum += c.angle;
        if (c.angle < min) min = c.angle;
        if (Math.abs(c.angle - target) <= rightAngleToleranceRad) nearRight++;
    }
    return {
        meanRad: sum / crossings.length,
        minRad: min === Infinity ? 0 : min,
        rightAngleRatio: nearRight / crossings.length,
    };
}

/**
 * M25 — type-pair decomposition of a crossing list.
 *
 * Returns:
 *   - distribution: `"typeA×typeB"` → count map (pair sorted lex)
 *   - topPairLabel: highest-count key, or `""` for empty input
 *   - topPairShare: highest-count count / total, or 0 for empty input
 *
 * Tie-breaking on top: lexicographic on the label key (deterministic across
 * runs, important for CSV stability).
 */
export function computeTypePairCrossingStats(
    crossings: CrossingInfo[],
): {
    distribution: Record<string, number>;
    topPairLabel: string;
    topPairShare: number;
} {
    if (crossings.length === 0) {
        return { distribution: {}, topPairLabel: '', topPairShare: 0 };
    }
    const distribution: Record<string, number> = {};
    for (const c of crossings) {
        const key = `${c.edgeAType}×${c.edgeBType}`;
        distribution[key] = (distribution[key] || 0) + 1;
    }
    let topLabel = '';
    let topCount = -1;
    for (const [key, count] of Object.entries(distribution)) {
        if (count > topCount || (count === topCount && key < topLabel)) {
            topCount = count;
            topLabel = key;
        }
    }
    return {
        distribution,
        topPairLabel: topLabel,
        topPairShare: topCount / crossings.length,
    };
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
 * M9 — Aspect ratio of the drawing's bounding box.
 *
 * Returns `min(w, h) / max(w, h)` ∈ [0, 1]. 1 is a perfect square; values
 * approaching 0 indicate a degenerately-elongated bbox. Returns 0 for
 * degenerate or empty bboxes (zero width/height).
 */
export function computeAspectRatio(
    bb: { minX: number; maxX: number; minY: number; maxY: number } | null,
): number {
    if (!bb) return 0;
    const w = bb.maxX - bb.minX;
    const h = bb.maxY - bb.minY;
    if (w <= 0 || h <= 0) return 0;
    return Math.min(w, h) / Math.max(w, h);
}

/**
 * M21 — Compound-parent cardinality scalars from a parent → member-count map.
 *
 * Pure helper so callers can supply counts gathered however they like (live
 * Cytoscape graph, fixture, or test data). Returns:
 *   - largestGroupSize: max children across compound parents
 *   - singletonFraction: parents with exactly 1 child / total parents
 *   - groups: per-parent (parentId, size) tuples for overlay badges
 *
 * Empty input returns zeros.
 */
export function computeCompoundCardinalityFromCounts(
    counts: Map<string, number>,
): CompoundCardinality {
    if (counts.size === 0) {
        return {
            largestGroupSize: 0,
            singletonFraction: 0,
            groupsCount: 0,
            sizeDistribution: {},
            groups: [],
        };
    }
    const sizes = Array.from(counts.values());
    const largestGroupSize = sizes.reduce((m, s) => (s > m ? s : m), 0);
    const singletons = sizes.filter(s => s === 1).length;
    const singletonFraction = singletons / sizes.length;
    const sizeDistribution: Record<number, number> = {};
    for (const s of sizes) {
        sizeDistribution[s] = (sizeDistribution[s] || 0) + 1;
    }
    const groups = Array.from(counts.entries()).map(([parentId, size]) => ({ parentId, size }));
    return {
        largestGroupSize,
        singletonFraction,
        groupsCount: counts.size,
        sizeDistribution,
        groups,
    };
}

/**
 * Type predicate for the synthetic debug-overlay nodes that should never
 * count toward graph metrics. Centralised so every metric path filters
 * the same set.
 */
function isDebugOverlayType(t: unknown): boolean {
    return t === 'CROSSING_DEBUG' || t === 'AREA_DEBUG' || t === 'UNIT_EDGE_NODE';
}

/**
 * M21 — Compound-parent cardinality computed from the live Cytoscape graph.
 * Aggregates visible non-debug nodes by their compound parent.
 */
export function computeCompoundCardinality(): CompoundCardinality {
    const cy = getCy();
    if (!cy) {
        return {
            largestGroupSize: 0,
            singletonFraction: 0,
            groupsCount: 0,
            sizeDistribution: {},
            groups: [],
        };
    }
    const counts = new Map<string, number>();
    cy.nodes(':visible').forEach(n => {
        if (isDebugOverlayType(n.data('type'))) return;
        // n.parent() returns a (possibly empty) Cytoscape collection
        const parents = n.parent();
        if (parents && parents.length > 0) {
            const pid = parents[0].id();
            counts.set(pid, (counts.get(pid) || 0) + 1);
        }
    });
    return computeCompoundCardinalityFromCounts(counts);
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
/**
 * Extra counts supplied by the caller (e.g. Trivy vulnerability total
 * which lives on the backend scan metadata, not on the live graph).
 */
export interface MetricsCsvContext {
    /** Sum of Trivy's per-package Vulnerabilities entries across loaded scans. */
    trivyVulnCount?: number;
}

export function metricsToCSV(m: DrawingMetrics, context: MetricsCsvContext = {}): string {
    const header = [
        'nodes',
        'edges',
        'unique_cves',
        'trivy_vuln_count',
        'crossings_raw',
        'crossings_normalized',
        'crossings_per_edge',
        'drawing_area',
        'area_per_node',
        'edge_length_cv',
        'aspect_ratio',
        'compound_groups_count',
        'compound_largest_group_size',
        'compound_singleton_fraction',
        'crossings_mean_angle_deg',
        'crossings_min_angle_deg',
        'crossings_right_angle_ratio',
        'crossings_top_pair_share',
        'crossings_top_pair_label',
        'stress_per_pair',
        'stress_per_pair_normalized_edge',
        'stress_per_pair_normalized_diagonal',
        'stress_per_pair_normalized_area',
        'stress_unreachable_pairs',
        'stress_reachable_pairs',
    ].join(',');
    const row = [
        m.nodes,
        m.edges,
        m.uniqueCves,
        context.trivyVulnCount ?? '',
        m.crossingsRaw,
        m.crossingsNormalized.toFixed(4),
        m.crossingsPerEdge.toFixed(4),
        m.drawingArea.toFixed(2),
        m.areaPerNode.toFixed(2),
        m.edgeLengthCV.toFixed(4),
        m.aspectRatio.toFixed(4),
        m.compoundGroupsCount,
        m.compoundLargestGroupSize,
        m.compoundSingletonFraction.toFixed(4),
        m.crossingsMeanAngleDeg.toFixed(2),
        m.crossingsMinAngleDeg.toFixed(2),
        m.crossingsRightAngleRatio.toFixed(4),
        m.crossingsTopPairShare.toFixed(4),
        csvEscape(m.crossingsTopPairLabel),
        m.stressPerPair.toFixed(2),
        m.stressPerPairNormalizedEdge.toFixed(4),
        m.stressPerPairNormalizedDiagonal.toFixed(4),
        m.stressPerPairNormalizedArea.toFixed(4),
        m.stressUnreachablePairs,
        m.stressReachablePairs,
    ].join(',');
    return header + '\n' + row + '\n';
}

/**
 * Trigger a CSV download in the browser.
 */
export function downloadMetricsCSV(m: DrawingMetrics, context: MetricsCsvContext = {}): void {
    const csv = metricsToCSV(m, context);
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

/**
 * RFC 4180 CSV field escape: wraps in double quotes when the value contains
 * a comma, double quote, or newline; doubles any embedded double quote.
 * Empty string → empty (not `""`) so absent fields don't add visual noise.
 */
function csvEscape(s: string): string {
    if (s === '') return '';
    if (/[",\n\r]/.test(s)) {
        return `"${s.replace(/"/g, '""')}"`;
    }
    return s;
}

function formatTimestamp(d: Date): string {
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}-${pad(d.getHours())}-${pad(d.getMinutes())}`;
}

// =============================================================================
// M1 — Stress (Purchase 2002, Kamada-Kawai-style aesthetic)
//
// Stress measures how well layout distances match graph (topology) distances.
// For every pair (i, j) of nodes, it sums the squared difference between
// the Euclidean distance in the layout and the shortest-path distance in
// the graph:
//
//     stress = Σ (‖p_i − p_j‖_layout − d_ij)²   over all reachable pairs
//
// We report the per-pair mean (size-normalised) plus the count of
// unreachable pairs (PAGDrawer graphs can be disconnected when visibility
// toggles partition them; per the metric_proposals.md "skip-and-report"
// convention, those pairs are excluded from the average and reported
// separately).
//
// Both M11 (k-NN preservation) and M12 (trustworthiness) need the same
// APSP matrix, so the helper is exposed and intended for reuse.
// =============================================================================

/**
 * All-pairs shortest paths via repeated BFS.
 *
 * **Defaults to directed** because PAGDrawer's graph is directed (an
 * attack graph: ATTACKER → HOST → CPE → CVE → CWE → TI → VC, plus
 * back-edges via ENABLES). Pass `{ directed: false }` to treat the
 * adjacency as undirected (what some Purchase-2002 stress variants
 * assume — but see `Docs/_domains/StressMetric.md` for why we don't
 * use that here).
 *
 * BFS is the right algorithm for an unweighted graph: O(|V|+|E|) per
 * source vs. Dijkstra's O(|E|+|V|log|V|) on the same input. Floyd-
 * Warshall would be O(|V|³), much worse for sparse graphs like ours.
 *
 * @param nodeIds  ids of every node to include (typically all visible
 *                 non-debug nodes).
 * @param edges    visible edges. Only the source/target ids are read;
 *                 geometry is ignored.
 * @param options  `directed: false` to treat edges as undirected.
 * @returns        Map<sourceId, Map<targetId, distance>>. Self-distance
 *                 is 0; unreachable pairs are absent from the inner map.
 *
 * Complexity: O(|V| · (|V| + |E|)). For PAGDrawer-sized graphs (~70 nodes,
 * ~90 edges) this is microseconds; for the largest scans (~500 nodes /
 * ~1000 edges) it is sub-second on the main thread.
 */
export function computeAPSP(
    nodeIds: string[],
    edges: Array<{ sourceId: string; targetId: string }>,
    options: { directed?: boolean } = {},
): Map<string, Map<string, number>> {
    const directed = options.directed !== false; // default true
    const result = new Map<string, Map<string, number>>();
    if (nodeIds.length === 0) return result;

    // Skip edges whose endpoint isn't in nodeIds — defensive against
    // debug-overlay edges or stale handles.
    const idSet = new Set(nodeIds);
    const adj = new Map<string, string[]>();
    for (const id of nodeIds) adj.set(id, []);
    for (const e of edges) {
        if (!idSet.has(e.sourceId) || !idSet.has(e.targetId)) continue;
        if (e.sourceId === e.targetId) continue; // self-loop: doesn't affect distances
        adj.get(e.sourceId)!.push(e.targetId);
        if (!directed) adj.get(e.targetId)!.push(e.sourceId);
    }

    // BFS from every node.
    for (const start of nodeIds) {
        const dist = new Map<string, number>();
        dist.set(start, 0);
        const queue: string[] = [start];
        let head = 0;
        while (head < queue.length) {
            const u = queue[head++];
            const d = dist.get(u)!;
            for (const v of adj.get(u)!) {
                if (!dist.has(v)) {
                    dist.set(v, d + 1);
                    queue.push(v);
                }
            }
        }
        result.set(start, dist);
    }
    return result;
}

/**
 * Symmetrise a directed APSP for a single unordered pair: returns the
 * shorter of the two directed paths, or `undefined` if neither direction
 * is reachable.
 *
 * Used by the stress metric — Euclidean layout distance is symmetric, so
 * the graph-side comparison must be too. See `Docs/_domains/StressMetric.md`
 * for the full justification.
 */
export function symmetrizedDistance(
    apsp: Map<string, Map<string, number>>,
    a: string,
    b: string,
): number | undefined {
    const dab = apsp.get(a)?.get(b);
    const dba = apsp.get(b)?.get(a);
    if (dab === undefined && dba === undefined) return undefined;
    if (dab === undefined) return dba;
    if (dba === undefined) return dab;
    return dab < dba ? dab : dba;
}

/**
 * M1 — Stress, normalised per pair, **symmetrised** for the directed
 * graph. See `Docs/_domains/StressMetric.md` for the rationale.
 *
 * For each unordered pair (i, j) we use the symmetrised graph distance
 * d_ij = min(d_directed(i→j), d_directed(j→i)), or treat the pair as
 * unreachable if neither direction has a path. The Euclidean distance
 * is intrinsically symmetric, so the graph-side comparison must be too —
 * otherwise every back-edge in the schema (ENABLES) would inflate the
 * unreachable count even though the layout couldn't possibly be wrong
 * about pairs that are visibly close.
 *
 * Pure function: takes node positions + a (directed) APSP matrix and
 * produces the stress scalars. Tests pass synthetic inputs without
 * needing a Cytoscape graph.
 *
 * @param layoutScale Divisor applied to the Euclidean layout distance
 *                    before the squared-difference is taken. Default 1
 *                    is the raw stress; pass `mean_edge_length` (KK
 *                    convention) or `sqrt(w²+h²)` (bbox diagonal) or
 *                    `sqrt(drawing_area)` for normalised variants. A
 *                    `layoutScale ≤ 0` short-circuits to all-zero
 *                    return so we never divide by zero on degenerate
 *                    layouts (single node, all coincident, etc.).
 *
 * Returns:
 *   - stressPerPair: mean of `((‖p_i − p_j‖_layout / layoutScale) − d_ij)²`
 *                    over reachable unordered pairs. 0 when fewer than
 *                    one reachable pair exists or layoutScale is invalid.
 *   - stressUnreachablePairs: count of unordered pairs where neither
 *                             direction has a path.
 *   - reachablePairCount: denominator used for the mean.
 *
 * Implementation note: only iterates the upper triangle (i < j) so each
 * unordered pair is counted once.
 */
export function computeStressFromAPSP(
    nodes: NodeWithPosition[],
    apsp: Map<string, Map<string, number>>,
    layoutScale: number = 1,
): { stressPerPair: number; stressUnreachablePairs: number; reachablePairCount: number } {
    const n = nodes.length;
    if (n < 2 || !(layoutScale > 0)) {
        // Note: also handle NaN / Infinity defensively via `!(scale > 0)`.
        // We still need to count unreachable pairs even for the degenerate
        // scale case, so a separate path computes them without summing.
        if (n < 2) return { stressPerPair: 0, stressUnreachablePairs: 0, reachablePairCount: 0 };
        let unreachable = 0;
        let reachable = 0;
        for (let i = 0; i < n; i++) {
            for (let j = i + 1; j < n; j++) {
                if (symmetrizedDistance(apsp, nodes[i].id, nodes[j].id) === undefined) unreachable++;
                else reachable++;
            }
        }
        return { stressPerPair: 0, stressUnreachablePairs: unreachable, reachablePairCount: reachable };
    }
    let sumSq = 0;
    let reachable = 0;
    let unreachable = 0;
    for (let i = 0; i < n; i++) {
        const a = nodes[i];
        for (let j = i + 1; j < n; j++) {
            const b = nodes[j];
            const dij = symmetrizedDistance(apsp, a.id, b.id);
            if (dij === undefined) {
                unreachable++;
                continue;
            }
            const dx = a.x - b.x;
            const dy = a.y - b.y;
            const layoutDist = Math.sqrt(dx * dx + dy * dy) / layoutScale;
            const diff = layoutDist - dij;
            sumSq += diff * diff;
            reachable++;
        }
    }
    return {
        stressPerPair: reachable > 0 ? sumSq / reachable : 0,
        stressUnreachablePairs: unreachable,
        reachablePairCount: reachable,
    };
}

export interface StressBundle {
    /** Raw stress per pair — unnormalised. Layout dist is in logical units. */
    raw: number;
    /**
     * Stress per pair after dividing layout distance by mean edge length
     * (Kamada-Kawai convention). Most cited in modern stress-majorization
     * literature; comparable across graphs with similar edge spacing.
     */
    normalizedEdge: number;
    /**
     * Stress per pair after dividing layout distance by the bbox diagonal
     * (`sqrt(w² + h²)`). Comparable across graphs of different drawing
     * sizes; rewards graphs whose pairs sit close-to-correctly within the
     * actual visible extent.
     */
    normalizedDiagonal: number;
    /**
     * Stress per pair after dividing layout distance by the square root
     * of the drawing area (`sqrt(w · h)` — geometric mean of the bbox
     * dimensions). Like the diagonal variant but biased toward "average
     * side length" rather than the corner-to-corner distance.
     */
    normalizedArea: number;
    /** Counts identical across all four — pair structure doesn't change. */
    unreachablePairs: number;
    reachablePairs: number;
}

/**
 * M1 — Stress computed from the live Cytoscape graph. Wraps `computeAPSP`
 * and `computeStressFromAPSP`, then runs the same APSP through three
 * normalisation scales (edge / bbox-diagonal / sqrt-area) so the JSON
 * export carries cross-graph-comparable stress values regardless of
 * which scaling convention the consuming paper / reader prefers.
 *
 * APSP is computed once and shared across all four stress evaluations.
 * Pair iteration is O(|V|²) per evaluation but the per-pair work is
 * trivial; even at |V|=1000 it's milliseconds.
 *
 * Future plans (M11/M12) may share the same APSP matrix via a within-
 * modal cache; for now it is recomputed on each `computeMetrics()` call.
 */
export function computeStress(): StressBundle {
    const empty: StressBundle = {
        raw: 0,
        normalizedEdge: 0,
        normalizedDiagonal: 0,
        normalizedArea: 0,
        unreachablePairs: 0,
        reachablePairs: 0,
    };
    const nodes = getVisibleNodesWithIds();
    if (nodes.length < 2) return empty;

    const edges = getVisibleEdgeEndpoints();
    const apsp = computeAPSP(nodes.map(n => n.id), edges);

    // Scale factors. mean_edge_length is computed on visible edges; bbox
    // dimensions on visible non-debug nodes. All three may be zero on
    // degenerate inputs (no edges → mean_edge_length=0; coincident nodes
    // → bbox 0×0). computeStressFromAPSP handles `≤ 0` defensively.
    const meanEdge = computeMeanEdgeLength(edges);
    const bbox = computeBoundingBox(nodes.map(n => ({ x: n.x, y: n.y })));
    const w = bbox ? bbox.maxX - bbox.minX : 0;
    const h = bbox ? bbox.maxY - bbox.minY : 0;
    const diagonal = Math.sqrt(w * w + h * h);
    const sqrtArea = Math.sqrt(w * h); // == sqrt(drawing_area)

    const raw = computeStressFromAPSP(nodes, apsp, 1);
    const edge = computeStressFromAPSP(nodes, apsp, meanEdge);
    const diag = computeStressFromAPSP(nodes, apsp, diagonal);
    const area = computeStressFromAPSP(nodes, apsp, sqrtArea);

    return {
        raw: raw.stressPerPair,
        normalizedEdge: edge.stressPerPair,
        normalizedDiagonal: diag.stressPerPair,
        normalizedArea: area.stressPerPair,
        unreachablePairs: raw.stressUnreachablePairs,
        reachablePairs: raw.reachablePairCount,
    };
}

// =============================================================================
// JSON export — schema v1
// =============================================================================
//
// Mirrors the CSV export but adds two things the CSV can't carry:
//   - A settings snapshot (granularity sliders, visibility, merge mode, ...)
//     so a downloaded JSON describes the graph state that produced its numbers.
//   - Build provenance (git SHA, app version) so the JSON traces back to the
//     exact code revision that ran.
//
// Schema versioning policy: bump `schema_version` only on breaking changes
// (renamed or removed keys). Adding new metric fields under `metrics` is
// non-breaking and stays at v1.
//
// =============================================================================

export interface DataSourceScanRef {
    id: string;
    name: string;
    vuln_count: number;
}

export interface DataSourceSnapshot {
    type: 'trivy' | 'mock' | 'unknown';
    scans_uploaded_total: number;
    /**
     * Scans that actually fed the current graph. When the user has selected
     * a subset (single-scan dropdown), this list contains only the chosen
     * scan(s). When the dropdown is on "all", this lists every uploaded scan
     * and `selection_was_implicit` is true.
     */
    scans_in_current_graph: DataSourceScanRef[];
    /**
     * `true` when the user did NOT explicitly choose a scan (the dropdown
     * was on "all"), so `scans_in_current_graph` was populated from the
     * full upload list. `false` when at least one specific scan was picked.
     */
    selection_was_implicit: boolean;
}

export interface MetricsJsonSnapshot {
    schema_version: 1;
    exported_at: string;       // ISO 8601 timestamp (UTC)
    app_version: string;
    git_sha: string;
    data_source: DataSourceSnapshot;
    settings: SettingsSnapshot;
    metrics: Record<string, unknown>;
}

/**
 * Build a DataSourceSnapshot from the full uploaded scan list and the
 * (optionally) user-selected subset.
 *
 * @param scans       Every scan currently uploaded to the backend.
 * @param selectedIds Scan IDs the user picked via the scan selector. Pass
 *                    `undefined` (or omit) when the user chose "all" — the
 *                    full upload list is used and `selection_was_implicit`
 *                    is set to `true`.
 *
 * `type` is heuristically Trivy if any scans exist; a future plan may add
 * explicit data-source typing.
 */
export function buildDataSourceSnapshot(
    scans: ScanInfo[],
    selectedIds?: string[] | null,
): DataSourceSnapshot {
    const explicit = Array.isArray(selectedIds) && selectedIds.length > 0;
    const selectedSet = explicit ? new Set(selectedIds) : null;
    const filtered = selectedSet
        ? scans.filter(s => selectedSet.has(s.id))
        : scans;

    return {
        type: scans.length > 0 ? 'trivy' : 'mock',
        scans_uploaded_total: scans.length,
        scans_in_current_graph: filtered.map(s => ({
            id: s.id,
            name: s.name,
            vuln_count: s.vuln_count,
        })),
        selection_was_implicit: !explicit,
    };
}

/**
 * Convert DrawingMetrics + caller context into the `metrics` sub-object of
 * the JSON export. Field names mirror the CSV columns for grep-friendliness;
 * types stay as native numbers (CSV stringifies; JSON should not).
 */
export function metricsToJsonObject(
    m: DrawingMetrics,
    context: MetricsCsvContext = {},
): Record<string, unknown> {
    return {
        nodes: m.nodes,
        edges: m.edges,
        unique_cves: m.uniqueCves,
        trivy_vuln_count: context.trivyVulnCount ?? null,
        crossings_raw: m.crossingsRaw,
        crossings_normalized: m.crossingsNormalized,
        crossings_per_edge: m.crossingsPerEdge,
        drawing_area: m.drawingArea,
        area_per_node: m.areaPerNode,
        edge_length_cv: m.edgeLengthCV,
        aspect_ratio: m.aspectRatio,
        compound_groups_count: m.compoundGroupsCount,
        compound_largest_group_size: m.compoundLargestGroupSize,
        compound_singleton_fraction: m.compoundSingletonFraction,
        compound_size_distribution: m.compoundSizeDistribution,
        crossings_mean_angle_deg: m.crossingsMeanAngleDeg,
        crossings_min_angle_deg: m.crossingsMinAngleDeg,
        crossings_right_angle_ratio: m.crossingsRightAngleRatio,
        crossings_top_pair_share: m.crossingsTopPairShare,
        crossings_top_pair_label: m.crossingsTopPairLabel,
        crossings_type_pair_distribution: m.crossingsTypePairDistribution,
        stress_per_pair: m.stressPerPair,
        stress_per_pair_normalized_edge: m.stressPerPairNormalizedEdge,
        stress_per_pair_normalized_diagonal: m.stressPerPairNormalizedDiagonal,
        stress_per_pair_normalized_area: m.stressPerPairNormalizedArea,
        stress_unreachable_pairs: m.stressUnreachablePairs,
        stress_reachable_pairs: m.stressReachablePairs,
    };
}

/**
 * Compose the full JSON metrics snapshot. Caller supplies the live settings
 * and data-source state so this function stays pure (testable without DOM).
 */
export function buildMetricsJsonSnapshot(
    m: DrawingMetrics,
    context: MetricsCsvContext,
    settings: SettingsSnapshot,
    dataSource: DataSourceSnapshot,
    now: Date = new Date(),
): MetricsJsonSnapshot {
    return {
        schema_version: 1,
        exported_at: now.toISOString(),
        app_version: getAppVersion(),
        git_sha: getGitSha(),
        data_source: dataSource,
        settings,
        metrics: metricsToJsonObject(m, context),
    };
}

/**
 * Stringify the snapshot with stable 2-space indentation (matches the
 * "diffable export" convention used elsewhere in the project).
 */
export function metricsToJSON(
    m: DrawingMetrics,
    context: MetricsCsvContext,
    settings: SettingsSnapshot,
    dataSource: DataSourceSnapshot,
    now: Date = new Date(),
): string {
    return JSON.stringify(buildMetricsJsonSnapshot(m, context, settings, dataSource, now), null, 2) + '\n';
}

/**
 * Trigger a JSON download in the browser. Filename mirrors the CSV
 * convention with a `.json` suffix.
 */
export function downloadMetricsJSON(
    m: DrawingMetrics,
    context: MetricsCsvContext,
    settings: SettingsSnapshot,
    dataSource: DataSourceSnapshot,
): void {
    const now = new Date();
    const json = metricsToJSON(m, context, settings, dataSource, now);
    const filename = `pagdrawer-metrics-${formatTimestamp(now)}.json`;

    const blob = new Blob([json], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}
