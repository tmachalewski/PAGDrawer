/**
 * Unit tests for constants module
 */

import { describe, it, expect } from 'vitest';
import { nodeColors, edgeColors, getCytoscapeStyles } from '../config/constants';

describe('Constants Module', () => {
    describe('nodeColors', () => {
        it('should have colors for all node types', () => {
            expect(nodeColors.HOST).toBeDefined();
            expect(nodeColors.CPE).toBeDefined();
            expect(nodeColors.CVE).toBeDefined();
            expect(nodeColors.CWE).toBeDefined();
            expect(nodeColors.TI).toBeDefined();
            expect(nodeColors.VC).toBeDefined();
            expect(nodeColors.ATTACKER).toBeDefined();
        });

        it('should return valid hex colors', () => {
            const hexColorRegex = /^#[0-9A-Fa-f]{6}$/;
            Object.values(nodeColors).forEach(color => {
                expect(color).toMatch(hexColorRegex);
            });
        });
    });

    describe('edgeColors', () => {
        it('should have colors for edge types', () => {
            expect(edgeColors.RUNS).toBeDefined();
            expect(edgeColors.HAS_VULN).toBeDefined();
            expect(edgeColors.CAN_REACH).toBeDefined();
        });
    });

    describe('getCytoscapeStyles', () => {
        it('should return an array of styles', () => {
            const styles = getCytoscapeStyles();
            expect(Array.isArray(styles)).toBe(true);
            expect(styles.length).toBeGreaterThan(0);
        });

        it('should have node and edge selectors', () => {
            const styles = getCytoscapeStyles();
            const selectors = styles.map(s => s.selector);
            expect(selectors).toContain('node');
            expect(selectors).toContain('edge');
        });
    });
});
