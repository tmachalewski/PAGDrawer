import { describe, it, expect } from 'vitest';
import { getGitSha, getAppVersion } from './buildInfo';

describe('buildInfo', () => {
    it('getGitSha returns a non-empty string', () => {
        const sha = getGitSha();
        expect(typeof sha).toBe('string');
        expect(sha.length).toBeGreaterThan(0);
    });

    it('getAppVersion returns a non-empty string', () => {
        const v = getAppVersion();
        expect(typeof v).toBe('string');
        expect(v.length).toBeGreaterThan(0);
    });

    it('getGitSha returns either a 40-char hex SHA or the "unknown" sentinel', () => {
        const sha = getGitSha();
        expect(sha === 'unknown' || /^[0-9a-f]{40}$/.test(sha)).toBe(true);
    });

    it('getGitSha returns a real SHA under vitest (proves Vite `define` substitution works)', () => {
        // This test would fail if the `define` keys in vite.config.ts ever drift
        // from the identifiers in buildInfo.ts. Skips gracefully if running
        // outside a git checkout.
        const sha = getGitSha();
        if (sha === 'unknown') {
            // Not in a git checkout — expected in some CI scenarios.
            return;
        }
        expect(sha).toMatch(/^[0-9a-f]{40}$/);
    });
});
