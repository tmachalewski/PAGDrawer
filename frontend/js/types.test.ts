/**
 * Unit tests for types module - verify type exports work correctly
 */

import { describe, it, expect } from 'vitest';
import type { Stats, GraphData } from './types';

describe('Types Module', () => {
    describe('Stats type', () => {
        it('should allow valid Stats objects', () => {
            const stats: Stats = {
                total_nodes: 100,
                total_edges: 150,
            };

            expect(stats.total_nodes).toBe(100);
            expect(stats.total_edges).toBe(150);
        });
    });

    describe('GraphData type', () => {
        it('should allow valid graph data structures', () => {
            const graphData: GraphData = {
                elements: {
                    nodes: [{ data: { id: 'n1', type: 'HOST', label: 'Server' } }],
                    edges: [{ data: { id: 'e1', source: 'n1', target: 'n2', type: 'RUNS' } }],
                },
            };

            expect(graphData.elements.nodes.length).toBe(1);
            expect(graphData.elements.edges.length).toBe(1);
        });
    });
});
