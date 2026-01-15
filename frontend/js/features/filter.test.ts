/**
 * Unit tests for filter module - test exports only
 * (Full integration testing is done via Playwright)
 */

import { describe, it, expect } from 'vitest';

describe('Filter Module Exports', () => {
    it('should export filterByType function', async () => {
        const module = await import('../features/filter');
        expect(module.filterByType).toBeDefined();
        expect(typeof module.filterByType).toBe('function');
    });

    it('should export setupFilterButtons function', async () => {
        const module = await import('../features/filter');
        expect(module.setupFilterButtons).toBeDefined();
        expect(typeof module.setupFilterButtons).toBe('function');
    });
});
