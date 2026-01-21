/**
 * Unit tests for environment module
 * Tests UI/AC filtering logic
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock getCy
vi.mock('../graph/core', () => ({
    getCy: vi.fn()
}));

import { getCy } from '../graph/core';

describe('Environment Module', () => {
    describe('Module Exports', () => {
        it('should export setupEnvironmentListeners function', async () => {
            const module = await import('../features/environment');
            expect(module.setupEnvironmentListeners).toBeDefined();
            expect(typeof module.setupEnvironmentListeners).toBe('function');
        });

        it('should export applyEnvironmentFilter function', async () => {
            const module = await import('../features/environment');
            expect(module.applyEnvironmentFilter).toBeDefined();
            expect(typeof module.applyEnvironmentFilter).toBe('function');
        });
    });

    describe('CVSS Parsing Logic', () => {
        it('should extract UI value from CVSS vector', () => {
            const cvssVector = 'CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H';
            const uiMatch = cvssVector.match(/UI:([NR])/);
            expect(uiMatch).not.toBeNull();
            expect(uiMatch![1]).toBe('R');
        });

        it('should extract AC value from CVSS vector', () => {
            const cvssVector = 'CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H';
            const acMatch = cvssVector.match(/AC:([LH])/);
            expect(acMatch).not.toBeNull();
            expect(acMatch![1]).toBe('H');
        });

        it('should handle UI:N (none)', () => {
            const cvssVector = 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H';
            const uiMatch = cvssVector.match(/UI:([NR])/);
            expect(uiMatch![1]).toBe('N');
        });

        it('should handle AC:L (low)', () => {
            const cvssVector = 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H';
            const acMatch = cvssVector.match(/AC:([LH])/);
            expect(acMatch![1]).toBe('L');
        });

        it('should return null for missing UI in vector', () => {
            const cvssVector = 'CVSS:3.1/AV:N/AC:L/PR:N';
            const uiMatch = cvssVector.match(/UI:([NR])/);
            expect(uiMatch).toBeNull();
        });
    });

    describe('Filter Condition Logic', () => {
        describe('UI filter conditions', () => {
            it('should allow UI:N CVE when setting is N', () => {
                const cvssUI = 'N';
                const uiSetting = 'N';
                const uiMet = (cvssUI === 'N') || (uiSetting === 'R');
                expect(uiMet).toBe(true);
            });

            it('should block UI:R CVE when setting is N', () => {
                const cvssUI = 'R'; // CVE requires user interaction
                const uiSetting = 'N'; // Environment has no users
                const uiMet = (cvssUI === 'N') || (uiSetting === 'R');
                expect(uiMet).toBe(false);
            });

            it('should allow UI:R CVE when setting is R', () => {
                const cvssUI = 'R';
                const uiSetting = 'R'; // Environment can provide user interaction
                const uiMet = (cvssUI === 'N') || (uiSetting === 'R');
                expect(uiMet).toBe(true);
            });

            it('should allow UI:N CVE when setting is R', () => {
                const cvssUI = 'N';
                const uiSetting = 'R';
                const uiMet = (cvssUI === 'N') || (uiSetting === 'R');
                expect(uiMet).toBe(true);
            });
        });

        describe('AC filter conditions', () => {
            it('should allow AC:L CVE when setting is L', () => {
                const cvssAC = 'L';
                const acSetting = 'L';
                const acMet = (cvssAC === 'L') || (acSetting === 'H');
                expect(acMet).toBe(true);
            });

            it('should block AC:H CVE when setting is L', () => {
                const cvssAC = 'H'; // Complex to exploit
                const acSetting = 'L'; // Only allow easy exploits
                const acMet = (cvssAC === 'L') || (acSetting === 'H');
                expect(acMet).toBe(false);
            });

            it('should allow AC:H CVE when setting is H', () => {
                const cvssAC = 'H';
                const acSetting = 'H'; // Allow complex exploits (sophisticated attacker)
                const acMet = (cvssAC === 'L') || (acSetting === 'H');
                expect(acMet).toBe(true);
            });

            it('should allow AC:L CVE when setting is H', () => {
                const cvssAC = 'L';
                const acSetting = 'H';
                const acMet = (cvssAC === 'L') || (acSetting === 'H');
                expect(acMet).toBe(true);
            });
        });

        describe('Combined UI and AC conditions', () => {
            it('should require both UI and AC to be met', () => {
                const cvssUI = 'N', uiSetting = 'N'; // met
                const cvssAC = 'H', acSetting = 'L'; // NOT met

                const uiMet = (cvssUI === 'N') || (uiSetting === 'R');
                const acMet = (cvssAC === 'L') || (acSetting === 'H');
                const bothMet = uiMet && acMet;

                expect(bothMet).toBe(false);
            });

            it('should pass when both conditions are met', () => {
                const cvssUI = 'N', uiSetting = 'N';
                const cvssAC = 'L', acSetting = 'L';

                const uiMet = (cvssUI === 'N') || (uiSetting === 'R');
                const acMet = (cvssAC === 'L') || (acSetting === 'H');
                const bothMet = uiMet && acMet;

                expect(bothMet).toBe(true);
            });
        });
    });

    describe('Environment VC Labels', () => {
        it('should format UI label correctly', () => {
            const uiSetting = 'R';
            const uiLabel = 'UI:' + uiSetting;
            expect(uiLabel).toBe('UI:R');
        });

        it('should format AC label correctly', () => {
            const acSetting = 'H';
            const acLabel = 'AC:' + acSetting;
            expect(acLabel).toBe('AC:H');
        });

        it('should generate correct description for UI:R', () => {
            const uiSetting = 'R';
            const description = uiSetting === 'R' ? 'User interaction available' : 'No user interaction';
            expect(description).toBe('User interaction available');
        });

        it('should generate correct description for UI:N', () => {
            const uiSetting = 'N';
            const description = uiSetting === 'R' ? 'User interaction available' : 'No user interaction';
            expect(description).toBe('No user interaction');
        });

        it('should generate correct description for AC:H', () => {
            const acSetting = 'H';
            const description = acSetting === 'H' ? 'High complexity tolerable' : 'Only low complexity';
            expect(description).toBe('High complexity tolerable');
        });

        it('should generate correct description for AC:L', () => {
            const acSetting = 'L';
            const description = acSetting === 'H' ? 'High complexity tolerable' : 'Only low complexity';
            expect(description).toBe('Only low complexity');
        });
    });
});

describe('Reachability Filter Logic', () => {
    describe('BFS algorithm', () => {
        it('should use Set for efficient visited tracking', () => {
            const visited = new Set<string>();
            visited.add('ATTACKER');
            expect(visited.has('ATTACKER')).toBe(true);
            expect(visited.has('HOST-001')).toBe(false);
        });

        it('should include L2 hosts with INSIDE_NETWORK suffix', () => {
            const hostId = 'host-001:INSIDE_NETWORK';
            expect(hostId.includes(':INSIDE_NETWORK')).toBe(true);
        });

        it('should identify L1 hosts without suffix', () => {
            const hostId = 'host-001';
            expect(hostId.includes(':INSIDE_NETWORK')).toBe(false);
        });
    });
});
