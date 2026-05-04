/**
 * Tests for settingsSnapshot.gatherCurrentSettings().
 *
 * Each source module is mocked so we can verify the snapshot reads from each
 * one independently and tolerates failures with sensible fallbacks.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { gatherCurrentSettings } from './settingsSnapshot';

// --- Mocks ---------------------------------------------------------------

vi.mock('../services/api', () => ({
    fetchConfig: vi.fn(),
}));
vi.mock('./filter', () => ({
    getHiddenTypes: vi.fn(),
}));
vi.mock('./cveMerge', () => ({
    getMergeMode: vi.fn(),
}));
vi.mock('./exploitPaths', () => ({
    isExploitPathsActive: vi.fn(),
}));
vi.mock('../graph/layout', () => ({
    getCurrentLayout: vi.fn(),
}));

import { fetchConfig } from '../services/api';
import { getHiddenTypes } from './filter';
import { getMergeMode } from './cveMerge';
import { isExploitPathsActive } from './exploitPaths';
import { getCurrentLayout } from '../graph/layout';

const mockedFetchConfig = vi.mocked(fetchConfig);
const mockedGetHiddenTypes = vi.mocked(getHiddenTypes);
const mockedGetMergeMode = vi.mocked(getMergeMode);
const mockedIsExploitPathsActive = vi.mocked(isExploitPathsActive);
const mockedGetCurrentLayout = vi.mocked(getCurrentLayout);

// --- DOM helpers ----------------------------------------------------------

function setSelect(id: string, value: string): void {
    const sel = document.createElement('select');
    sel.id = id;
    const opt = document.createElement('option');
    opt.value = value;
    opt.textContent = value;
    sel.appendChild(opt);
    sel.value = value;
    document.body.appendChild(sel);
}

function setCheckbox(id: string, checked: boolean): void {
    const inp = document.createElement('input');
    inp.type = 'checkbox';
    inp.id = id;
    inp.checked = checked;
    document.body.appendChild(inp);
}

beforeEach(() => {
    document.body.innerHTML = '';
    vi.clearAllMocks();

    // Reasonable defaults for the happy path
    mockedFetchConfig.mockResolvedValue({
        HOST: 'ATTACKER',
        CPE: 'HOST',
        CVE: 'CPE',
        CWE: 'CVE',
        TI: 'CWE',
        VC: 'TI',
        skip_layer_2: false,
    });
    mockedGetHiddenTypes.mockReturnValue(new Set(['CWE', 'TI']));
    mockedGetMergeMode.mockReturnValue('outcomes' as any);
    mockedIsExploitPathsActive.mockReturnValue(false);
    mockedGetCurrentLayout.mockReturnValue('dagre');
});

// --- Tests ----------------------------------------------------------------

describe('gatherCurrentSettings', () => {
    it('captures granularity and skip_layer_2 from /api/config', async () => {
        mockedFetchConfig.mockResolvedValue({
            HOST: 'ATTACKER',
            CPE: 'HOST',
            CVE: 'HOST',
            CWE: 'CVE',
            TI: 'CWE',
            VC: 'TI',
            skip_layer_2: true,
        });

        const snap = await gatherCurrentSettings();

        expect(snap.granularity).toEqual({
            HOST: 'ATTACKER',
            CPE: 'HOST',
            CVE: 'HOST',
            CWE: 'CVE',
            TI: 'CWE',
            VC: 'TI',
        });
        expect(snap.skip_layer_2).toBe(true);
    });

    it('captures sorted visibility_hidden array', async () => {
        mockedGetHiddenTypes.mockReturnValue(new Set(['TI', 'CWE', 'VC']));
        const snap = await gatherCurrentSettings();
        expect(snap.visibility_hidden).toEqual(['CWE', 'TI', 'VC']); // sorted
    });

    it('captures cve_merge_mode', async () => {
        mockedGetMergeMode.mockReturnValue('prereqs' as any);
        const snap = await gatherCurrentSettings();
        expect(snap.cve_merge_mode).toBe('prereqs');
    });

    it('captures environment_filter from DOM selects', async () => {
        setSelect('env-ui', 'N');
        setSelect('env-ac', 'L');
        const snap = await gatherCurrentSettings();
        expect(snap.environment_filter).toEqual({ ui: 'N', ac: 'L' });
    });

    it('environment_filter is null/null when DOM selects are missing', async () => {
        const snap = await gatherCurrentSettings();
        expect(snap.environment_filter).toEqual({ ui: null, ac: null });
    });

    it('captures exploit_paths_active boolean', async () => {
        mockedIsExploitPathsActive.mockReturnValue(true);
        const snap = await gatherCurrentSettings();
        expect(snap.exploit_paths_active).toBe(true);
    });

    it('captures force_refresh_on_last_rebuild from DOM checkbox', async () => {
        setCheckbox('force-refresh-checkbox', true);
        const snap = await gatherCurrentSettings();
        expect(snap.force_refresh_on_last_rebuild).toBe(true);
    });

    it('force_refresh defaults to false when checkbox is missing', async () => {
        const snap = await gatherCurrentSettings();
        expect(snap.force_refresh_on_last_rebuild).toBe(false);
    });

    it('captures current layout name', async () => {
        mockedGetCurrentLayout.mockReturnValue('cose');
        const snap = await gatherCurrentSettings();
        expect(snap.layout).toBe('cose');
    });

    it('falls back to sentinel defaults when fetchConfig rejects', async () => {
        mockedFetchConfig.mockRejectedValue(new Error('network down'));
        const snap = await gatherCurrentSettings();
        expect(snap.granularity).toEqual({});
        expect(snap.skip_layer_2).toBe(false);
    });

    it('produces a fully-populated snapshot for the happy path', async () => {
        const snap = await gatherCurrentSettings();
        // Schema sanity: every documented top-level key is present
        expect(Object.keys(snap).sort()).toEqual([
            'cve_merge_mode',
            'environment_filter',
            'exploit_paths_active',
            'force_refresh_on_last_rebuild',
            'granularity',
            'layout',
            'skip_layer_2',
            'visibility_hidden',
        ]);
    });
});
