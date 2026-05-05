/**
 * Locks in the merge-key shapes after extraction from cveMerge.ts.
 *
 * The merge mechanism's tests (cveMerge.test.ts) cover the END-TO-END
 * grouping behaviour (CVEs that share a key end up in the same compound).
 * This file targets the KEY STRINGS themselves — both as a regression
 * guard against future churn in the format and so the M22 metric can be
 * tested against a stable contract.
 */

import { describe, it, expect } from 'vitest';
import {
    computePrereqKeyFromData,
    computeOutcomeKeyFromData,
    formatMergeLabel,
} from './mergeKeys';

describe('computePrereqKeyFromData', () => {
    it('joins prereqs into a stable pipe-delimited key', () => {
        const k = computePrereqKeyFromData({
            prereqs: { AV: 'N', AC: 'L', PR: 'N', UI: 'N' },
            chain_depth: 0,
            layer: 'L1',
        });
        expect(k).toBe('AV:N|AC:L|PR:N|UI:N|L1|d0');
    });

    it('encodes layer and chain_depth in the suffix', () => {
        const k = computePrereqKeyFromData({
            prereqs: { AV: 'L', AC: 'H', PR: 'L', UI: 'R' },
            chain_depth: 2,
            layer: 'L2',
        });
        expect(k).toBe('AV:L|AC:H|PR:L|UI:R|L2|d2');
    });

    it('returns "unknown" sentinel when prereqs are missing', () => {
        expect(computePrereqKeyFromData({ chain_depth: 0, layer: 'L1' })).toBe('unknown|L1|d0');
        expect(computePrereqKeyFromData({ prereqs: null, chain_depth: 1, layer: 'L2' })).toBe('unknown|L2|d1');
    });

    it('defaults chain_depth=0 and layer=L1 when omitted', () => {
        expect(computePrereqKeyFromData({
            prereqs: { AV: 'N', AC: 'L', PR: 'N', UI: 'N' },
        })).toBe('AV:N|AC:L|PR:N|UI:N|L1|d0');
    });
});

describe('computeOutcomeKeyFromData', () => {
    it('joins outcomes into a comma-delimited key, preserving order', () => {
        const k = computeOutcomeKeyFromData({
            vc_outcomes: [['AV', 'L'], ['EX', 'Y'], ['PR', 'H']],
            chain_depth: 0,
            layer: 'L1',
        });
        expect(k).toBe('AV:L,EX:Y,PR:H|L1|d0');
    });

    it('returns "none" sentinel when outcomes is empty', () => {
        expect(computeOutcomeKeyFromData({
            vc_outcomes: [],
            chain_depth: 0,
            layer: 'L1',
        })).toBe('none|L1|d0');
    });

    it('returns "unknown" sentinel when outcomes is missing/non-array', () => {
        expect(computeOutcomeKeyFromData({ chain_depth: 0, layer: 'L1' })).toBe('unknown|L1|d0');
        expect(computeOutcomeKeyFromData({
            vc_outcomes: null,
            chain_depth: 0,
            layer: 'L1',
        })).toBe('unknown|L1|d0');
    });

    it('encodes layer and chain_depth in the suffix', () => {
        expect(computeOutcomeKeyFromData({
            vc_outcomes: [['A', 'L']],
            chain_depth: 3,
            layer: 'L2',
        })).toBe('A:L|L2|d3');
    });
});

describe('formatMergeLabel', () => {
    it('prereqs: pipe-separated with × suffix', () => {
        const label = formatMergeLabel('AV:N|AC:L|PR:N|UI:N|L1|d0', 6, 'prereqs');
        expect(label).toBe('AV:N / AC:L / PR:N / UI:N (×6)');
    });

    it('outcomes: arrow + comma-separated with × suffix', () => {
        const label = formatMergeLabel('AV:L,EX:Y,PR:H|L1|d0', 3, 'outcomes');
        expect(label).toBe('→ AV:L, EX:Y, PR:H (×3)');
    });

    it('outcomes "none" sentinel renders as "no VCs"', () => {
        const label = formatMergeLabel('none|L1|d0', 4, 'outcomes');
        expect(label).toBe('→ no VCs (×4)');
    });

    it('strips layer/depth suffix before display', () => {
        // "L2|d3" should not appear in any rendered label
        expect(formatMergeLabel('AV:N|L2|d3', 1, 'prereqs')).not.toContain('L2');
        expect(formatMergeLabel('AV:N|L2|d3', 1, 'prereqs')).not.toContain('d3');
    });
});
