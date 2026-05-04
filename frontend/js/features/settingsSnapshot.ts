/**
 * Snapshot of every user-controllable input that affects the displayed graph
 * at the moment of metrics computation. Bundled into the JSON metrics export
 * so a downloaded file is, in principle, reproducible — re-applying the
 * settings to the same data should produce the same metrics.
 *
 * Sources (one per field; each wrapped in a try/catch so a single missing
 * source produces a sentinel default rather than failing the whole export):
 *
 *   granularity / skip_layer_2  ← fetchConfig() (backend /api/config)
 *   visibility_hidden           ← getHiddenTypes() (filter.ts)
 *   cve_merge_mode              ← getMergeMode() (cveMerge.ts)
 *   environment_filter          ← DOM <select id="env-ui">, <select id="env-ac">
 *   exploit_paths_active        ← isExploitPathsActive() (exploitPaths.ts)
 *   force_refresh_on_last_rebuild ← DOM <input id="force-refresh-checkbox">
 *   layout                      ← getCurrentLayout() (layout.ts)
 *
 * Things deliberately NOT captured (out of scope for reproducibility):
 *   - Window size / zoom / pan: zoom-invariant by design.
 *   - Light vs dark theme: cosmetic.
 *   - Selected nodes: analyst-session ephemera.
 *   - Exploit-paths seed selection: documented gap; reproducibility for
 *     exploit-paths-active states requires the user to re-trigger the seed.
 */

import { fetchConfig } from '../services/api';
import { getHiddenTypes } from './filter';
import { getMergeMode } from './cveMerge';
import { isExploitPathsActive } from './exploitPaths';
import { getCurrentLayout } from '../graph/layout';

export interface GranularitySettings {
    HOST?: string;
    CPE?: string;
    CVE?: string;
    CWE?: string;
    TI?: string;
    VC?: string;
}

export interface EnvironmentFilter {
    ui: string | null;
    ac: string | null;
}

export interface SettingsSnapshot {
    granularity: GranularitySettings;
    skip_layer_2: boolean;
    visibility_hidden: string[];      // sorted, deterministic
    cve_merge_mode: string;            // "none" | "prereqs" | "outcomes" (from MergeMode)
    environment_filter: EnvironmentFilter;
    exploit_paths_active: boolean;
    force_refresh_on_last_rebuild: boolean;
    layout: string;                    // "dagre" | "breadthfirst" | "cose" | "circle"
}

/**
 * Read a DOM <select> value. Returns `null` if the element is missing or the
 * value is the empty string.
 */
function readSelect(id: string): string | null {
    if (typeof document === 'undefined') return null;
    const el = document.getElementById(id) as HTMLSelectElement | null;
    if (!el) return null;
    return el.value === '' ? null : el.value;
}

function readCheckbox(id: string): boolean {
    if (typeof document === 'undefined') return false;
    const el = document.getElementById(id) as HTMLInputElement | null;
    if (!el) return false;
    return !!el.checked;
}

/**
 * Read the backend /api/config payload and split it into granularity (the
 * per-node-type grouping levels) plus the standalone skip_layer_2 flag.
 * Returns sentinel defaults on network failure.
 */
async function readConfig(): Promise<{ granularity: GranularitySettings; skip_layer_2: boolean }> {
    try {
        const cfg = await fetchConfig();
        const granularity: GranularitySettings = {};
        const knownKeys: Array<keyof GranularitySettings> = ['HOST', 'CPE', 'CVE', 'CWE', 'TI', 'VC'];
        for (const k of knownKeys) {
            const v = cfg[k];
            if (typeof v === 'string') granularity[k] = v;
        }
        const skip_layer_2 = !!cfg.skip_layer_2;
        return { granularity, skip_layer_2 };
    } catch (err) {
        console.error('settingsSnapshot: fetchConfig failed:', err);
        return { granularity: {}, skip_layer_2: false };
    }
}

function readVisibilityHidden(): string[] {
    try {
        return Array.from(getHiddenTypes()).sort();
    } catch {
        return [];
    }
}

function readMergeMode(): string {
    try {
        return String(getMergeMode());
    } catch {
        return 'none';
    }
}

function readExploitPathsActive(): boolean {
    try {
        return !!isExploitPathsActive();
    } catch {
        return false;
    }
}

function readLayout(): string {
    try {
        return String(getCurrentLayout());
    } catch {
        return 'dagre';
    }
}

/**
 * Gather a complete settings snapshot. Async because the backend config is
 * fetched once per call. Callers should snapshot at the same moment they
 * compute metrics so the JSON export's settings match the reported numbers.
 */
export async function gatherCurrentSettings(): Promise<SettingsSnapshot> {
    const { granularity, skip_layer_2 } = await readConfig();
    return {
        granularity,
        skip_layer_2,
        visibility_hidden: readVisibilityHidden(),
        cve_merge_mode: readMergeMode(),
        environment_filter: {
            ui: readSelect('env-ui'),
            ac: readSelect('env-ac'),
        },
        exploit_paths_active: readExploitPathsActive(),
        force_refresh_on_last_rebuild: readCheckbox('force-refresh-checkbox'),
        layout: readLayout(),
    };
}
