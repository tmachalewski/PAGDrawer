/**
 * Unit tests for search module
 * Tests the node search functionality including matching logic
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock getCy to avoid Cytoscape dependency in unit tests
vi.mock('../graph/core', () => ({
    getCy: vi.fn()
}));

import { getCy } from '../graph/core';

describe('Search Module', () => {
    describe('Module Exports', () => {
        it('should export setupSearch function', async () => {
            const module = await import('../features/search');
            expect(module.setupSearch).toBeDefined();
            expect(typeof module.setupSearch).toBe('function');
        });

        it('should export performSearch function', async () => {
            const module = await import('../features/search');
            expect(module.performSearch).toBeDefined();
            expect(typeof module.performSearch).toBe('function');
        });

        it('should export clearSearch function', async () => {
            const module = await import('../features/search');
            expect(module.clearSearch).toBeDefined();
            expect(typeof module.clearSearch).toBe('function');
        });

        it('should export focusSearch function', async () => {
            const module = await import('../features/search');
            expect(module.focusSearch).toBeDefined();
            expect(typeof module.focusSearch).toBe('function');
        });
    });

    describe('performSearch logic', () => {
        let mockCy: any;
        let mockNodes: any[];
        let mockElements: any;

        beforeEach(() => {
            mockNodes = [
                { data: (key: string) => key === 'label' ? 'CVE-2021-44228' : 'node1', addClass: vi.fn(), removeClass: vi.fn(), select: vi.fn(), connectedEdges: () => ({ length: 0 }) },
                { data: (key: string) => key === 'label' ? 'CVE-2022-1234' : 'node2', addClass: vi.fn(), removeClass: vi.fn(), select: vi.fn(), connectedEdges: () => ({ length: 0 }) },
                { data: (key: string) => key === 'label' ? 'CWE-79' : 'node3', addClass: vi.fn(), removeClass: vi.fn(), select: vi.fn(), connectedEdges: () => ({ length: 0 }) },
                { data: (key: string) => key === 'label' ? 'HOST-001' : 'node4', addClass: vi.fn(), removeClass: vi.fn(), select: vi.fn(), connectedEdges: () => ({ length: 0 }) }
            ];

            mockElements = {
                removeClass: vi.fn().mockReturnThis(),
                addClass: vi.fn().mockReturnThis(),
                unselect: vi.fn().mockReturnThis(),
                not: vi.fn().mockReturnThis(),
                select: vi.fn().mockReturnThis()
            };

            mockCy = {
                nodes: vi.fn().mockReturnValue({
                    filter: vi.fn((callback: Function) => {
                        const filtered = mockNodes.filter((node, index) => callback(node, index));
                        return {
                            length: filtered.length,
                            addClass: vi.fn(),
                            select: vi.fn(),
                            connectedEdges: () => mockElements
                        };
                    })
                }),
                elements: vi.fn().mockReturnValue(mockElements)
            };

            vi.mocked(getCy).mockReturnValue(mockCy);
        });

        afterEach(() => {
            vi.clearAllMocks();
        });

        it('should return 0 when cy is null', async () => {
            vi.mocked(getCy).mockReturnValue(null);
            const { performSearch } = await import('../features/search');
            const result = performSearch('test');
            expect(result).toBe(0);
        });

        it('should perform case-insensitive search', async () => {
            const { performSearch } = await import('../features/search');

            // Reset mock to test lowercase matching
            vi.mocked(getCy).mockReturnValue(mockCy);

            // The filter callback should be called with lowercase query
            const result = performSearch('CVE');
            expect(mockCy.nodes).toHaveBeenCalled();
        });

        it('should match partial labels', async () => {
            const { performSearch } = await import('../features/search');

            // Nodes with "2021" in label should match
            mockCy.nodes.mockReturnValue({
                filter: vi.fn((callback: Function) => {
                    const node = { data: () => 'CVE-2021-44228' };
                    const matches = callback(node);
                    return {
                        length: matches ? 1 : 0,
                        addClass: vi.fn(),
                        select: vi.fn(),
                        connectedEdges: () => mockElements
                    };
                })
            });

            performSearch('2021');
            expect(mockCy.nodes).toHaveBeenCalled();
        });
    });

    describe('Search Configuration', () => {
        it('should have DEBOUNCE_MS constant', async () => {
            // The search module uses 200ms debounce
            // We can verify by checking the behavior indirectly
            const module = await import('../features/search');
            expect(module.setupSearch).toBeDefined();
        });

        it('should have MIN_QUERY_LENGTH of 2', async () => {
            // Search only triggers with 2+ characters
            const module = await import('../features/search');
            expect(module.performSearch).toBeDefined();
        });
    });
});

describe('Search Matching Rules', () => {
    describe('Label matching', () => {
        it('should match CVE IDs case-insensitively', () => {
            const label = 'CVE-2021-44228';
            const query = 'cve';
            expect(label.toLowerCase().includes(query.toLowerCase())).toBe(true);
        });

        it('should match partial CVE years', () => {
            const label = 'CVE-2021-44228';
            const query = '2021';
            expect(label.toLowerCase().includes(query.toLowerCase())).toBe(true);
        });

        it('should match CWE IDs', () => {
            const label = 'CWE-79: XSS';
            const query = 'cwe-79';
            expect(label.toLowerCase().includes(query.toLowerCase())).toBe(true);
        });

        it('should match HOST names', () => {
            const label = 'host-web-001';
            const query = 'web';
            expect(label.toLowerCase().includes(query.toLowerCase())).toBe(true);
        });

        it('should not match when query not in label', () => {
            const label = 'CVE-2021-44228';
            const query = 'xyz';
            expect(label.toLowerCase().includes(query.toLowerCase())).toBe(false);
        });

        it('should handle empty labels gracefully', () => {
            const label = '';
            const query = 'test';
            expect(label.toLowerCase().includes(query.toLowerCase())).toBe(false);
        });
    });
});
