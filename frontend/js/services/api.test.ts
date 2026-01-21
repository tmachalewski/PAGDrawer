/**
 * Unit tests for API service module
 * Tests API functions with mocked fetch
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock global fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('API Service Module', () => {
    beforeEach(() => {
        mockFetch.mockClear();
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    describe('Module Exports', () => {
        it('should export fetchGraph function', async () => {
            const api = await import('../services/api');
            expect(api.fetchGraph).toBeDefined();
            expect(typeof api.fetchGraph).toBe('function');
        });

        it('should export fetchStats function', async () => {
            const api = await import('../services/api');
            expect(api.fetchStats).toBeDefined();
            expect(typeof api.fetchStats).toBe('function');
        });

        it('should export fetchConfig function', async () => {
            const api = await import('../services/api');
            expect(api.fetchConfig).toBeDefined();
            expect(typeof api.fetchConfig).toBe('function');
        });

        it('should export updateConfig function', async () => {
            const api = await import('../services/api');
            expect(api.updateConfig).toBeDefined();
            expect(typeof api.updateConfig).toBe('function');
        });

        it('should export uploadTrivyFile function', async () => {
            const api = await import('../services/api');
            expect(api.uploadTrivyFile).toBeDefined();
            expect(typeof api.uploadTrivyFile).toBe('function');
        });

        it('should export rebuildData function', async () => {
            const api = await import('../services/api');
            expect(api.rebuildData).toBeDefined();
            expect(typeof api.rebuildData).toBe('function');
        });

        it('should export resetData function', async () => {
            const api = await import('../services/api');
            expect(api.resetData).toBeDefined();
            expect(typeof api.resetData).toBe('function');
        });

        it('should export getDataStatus function', async () => {
            const api = await import('../services/api');
            expect(api.getDataStatus).toBeDefined();
            expect(typeof api.getDataStatus).toBe('function');
        });

        it('should export getScans function', async () => {
            const api = await import('../services/api');
            expect(api.getScans).toBeDefined();
            expect(typeof api.getScans).toBe('function');
        });

        it('should export deleteScan function', async () => {
            const api = await import('../services/api');
            expect(api.deleteScan).toBeDefined();
            expect(typeof api.deleteScan).toBe('function');
        });
    });

    describe('fetchGraph', () => {
        it('should call /api/graph endpoint', async () => {
            const mockResponse = {
                elements: { nodes: [], edges: [] }
            };
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(mockResponse)
            });

            const { fetchGraph } = await import('../services/api');
            const result = await fetchGraph();

            expect(mockFetch).toHaveBeenCalledWith('/api/graph');
            expect(result).toEqual(mockResponse);
        });

        it('should throw on non-ok response', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 500
            });

            const { fetchGraph } = await import('../services/api');
            await expect(fetchGraph()).rejects.toThrow('Failed to fetch graph: 500');
        });
    });

    describe('fetchStats', () => {
        it('should call /api/stats endpoint', async () => {
            const mockStats = {
                total_nodes: 100,
                total_edges: 150,
                nodes_by_type: { HOST: 10 }
            };
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(mockStats)
            });

            const { fetchStats } = await import('../services/api');
            const result = await fetchStats();

            expect(mockFetch).toHaveBeenCalledWith('/api/stats');
            expect(result).toEqual(mockStats);
        });

        it('should throw on non-ok response', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 404
            });

            const { fetchStats } = await import('../services/api');
            await expect(fetchStats()).rejects.toThrow('Failed to fetch stats: 404');
        });
    });

    describe('updateConfig', () => {
        it('should POST to /api/config with JSON body', async () => {
            const mockResponse = { status: 'ok', stats: {} };
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(mockResponse)
            });

            const { updateConfig } = await import('../services/api');
            const config = { TI: 'ATTACKER', VC: 'HOST' };
            await updateConfig(config);

            expect(mockFetch).toHaveBeenCalledWith('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
        });
    });

    describe('rebuildData', () => {
        it('should POST to /api/data/rebuild with query params', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ status: 'ok' })
            });

            const { rebuildData } = await import('../services/api');
            await rebuildData(true);

            expect(mockFetch).toHaveBeenCalledWith(
                expect.stringContaining('/api/data/rebuild'),
                { method: 'POST' }
            );
        });

        it('should include scan_ids in query params when provided', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ status: 'ok' })
            });

            const { rebuildData } = await import('../services/api');
            await rebuildData(true, ['scan1', 'scan2']);

            const callUrl = mockFetch.mock.calls[0][0];
            expect(callUrl).toContain('scan_ids=scan1');
            expect(callUrl).toContain('scan_ids=scan2');
        });
    });

    describe('resetData', () => {
        it('should POST to /api/data/reset', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ status: 'ok', source: 'mock' })
            });

            const { resetData } = await import('../services/api');
            await resetData();

            expect(mockFetch).toHaveBeenCalledWith('/api/data/reset', { method: 'POST' });
        });
    });

    describe('deleteScan', () => {
        it('should DELETE to /api/data/scans/{id}', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ status: 'deleted', remaining: 0 })
            });

            const { deleteScan } = await import('../services/api');
            await deleteScan('scan123');

            expect(mockFetch).toHaveBeenCalledWith('/api/data/scans/scan123', {
                method: 'DELETE'
            });
        });
    });
});

describe('API Error Handling', () => {
    beforeEach(() => {
        mockFetch.mockClear();
    });

    it('should include status code in error message', async () => {
        mockFetch.mockResolvedValueOnce({
            ok: false,
            status: 503
        });

        const { fetchGraph } = await import('../services/api');
        await expect(fetchGraph()).rejects.toThrow('503');
    });

    it('should handle network errors', async () => {
        mockFetch.mockRejectedValueOnce(new Error('Network error'));

        const { fetchGraph } = await import('../services/api');
        await expect(fetchGraph()).rejects.toThrow('Network error');
    });
});
