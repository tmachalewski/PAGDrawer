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
}

export interface CompoundCardinality {
    largestGroupSize: number;
    singletonFraction: number;
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

    // 2. Drawing area (center-point bounding box) + M9 aspect ratio
    const bbox = computeBoundingBox(points);
    const drawingArea = computeDrawingArea(points);
    const areaPerNode = nodeCount > 0 ? drawingArea / nodeCount : 0;
    const aspectRatio = computeAspectRatio(bbox);

    // 3. Edge length CV
    const edgeLengthCV = computeEdgeLengthCV(edges);

    // 5. M21 — compound-parent cardinality (largest group + singleton fraction)
    const compound = computeCompoundCardinality();

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
        return { largestGroupSize: 0, singletonFraction: 0, groups: [] };
    }
    const sizes = Array.from(counts.values());
    const largestGroupSize = sizes.reduce((m, s) => (s > m ? s : m), 0);
    const singletons = sizes.filter(s => s === 1).length;
    const singletonFraction = singletons / sizes.length;
    const groups = Array.from(counts.entries()).map(([parentId, size]) => ({ parentId, size }));
    return { largestGroupSize, singletonFraction, groups };
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
    if (!cy) return { largestGroupSize: 0, singletonFraction: 0, groups: [] };
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
        'compound_largest_group_size',
        'compound_singleton_fraction',
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
        m.compoundLargestGroupSize,
        m.compoundSingletonFraction.toFixed(4),
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

function formatTimestamp(d: Date): string {
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}-${pad(d.getHours())}-${pad(d.getMinutes())}`;
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
    scans_in_current_graph: DataSourceScanRef[];
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
 * Build a DataSourceSnapshot from the list of scans currently uploaded.
 * For now `type` is heuristically Trivy if any scans exist; a future plan
 * may add explicit data-source typing.
 */
export function buildDataSourceSnapshot(scans: ScanInfo[]): DataSourceSnapshot {
    return {
        type: scans.length > 0 ? 'trivy' : 'mock',
        scans_uploaded_total: scans.length,
        scans_in_current_graph: scans.map(s => ({
            id: s.id,
            name: s.name,
            vuln_count: s.vuln_count,
        })),
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
        compound_largest_group_size: m.compoundLargestGroupSize,
        compound_singleton_fraction: m.compoundSingletonFraction,
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
