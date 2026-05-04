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
});
