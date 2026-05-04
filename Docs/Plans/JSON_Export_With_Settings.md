# JSON Export with Settings Snapshot — Implementation Plan

**Created:** 2026-05-03-21-42
**Branch (proposed):** `feature/metrics-roadmap-json-export` (sub-branch of the umbrella `feature/metrics-roadmap`; see Master roadmap)
**Sister plans:** `Debug_Overlay_Visualizations.md`, `Paper_Evaluation_Metrics.md`

---

## Goal

Extend the Statistics modal's CSV export with a parallel **JSON export** option. The JSON file contains:

1. The same metric values that the CSV export contains (one-row equivalent)
2. A **settings snapshot** describing the graph state at export time — granularity sliders, visibility toggles, CVE merge mode, environment filter, exploit-paths state, scan selection, etc.
3. Bookkeeping metadata — timestamp, app version, source data identifier

The CSV export is unchanged and remains the default for spreadsheet workflows. JSON is for programmatic post-processing, archival, and reproducibility.

---

## Why JSON, in addition to CSV

| Concern | CSV | JSON |
|---------|-----|------|
| Spreadsheet-native | ✅ | ❌ |
| Nested structures (settings tree) | ❌ | ✅ |
| Type fidelity (numbers vs strings, nulls) | ❌ | ✅ |
| Nested objects (e.g., M26's per-edge-type breakdown) | flat-columns workaround | natural single nested object |
| Reproducibility (settings recoverable from the export) | ❌ | ✅ |

The two formats coexist; the user picks per export.

---

## File Format

**Filename**: `pagdrawer-metrics-YYYY-MM-DD-HH-mm.json` (mirrors the CSV filename, .json suffix)

**Schema** (illustrative; field set grows as new metrics ship in the sister plans):

```json
{
  "schema_version": 1,
  "exported_at": "2026-05-03T21:42:11.000Z",
  "app_version": "2.1.0",
  "git_sha": "fa9e45dc8a3b1e2f0c4d5a7b9e6f8a2c4b1d3e5f",

  "data_source": {
    "type": "trivy",
    "scans_uploaded_total": 3,
    "scans_in_current_graph": [
      { "id": "scan-uuid-1", "name": "nginx:stable-trixie-perl", "vuln_count": 189 }
    ]
  },

  "settings": {
    "granularity": {
      "HOST": "ATTACKER",
      "CPE":  "HOST",
      "CVE":  "CPE",
      "CWE":  "CVE",
      "TI":   "CWE",
      "VC":   "TI"
    },
    "skip_layer_2": false,
    "visibility_hidden": ["CWE", "TI"],
    "cve_merge_mode": "outcomes",
    "environment_filter": { "ui": "N", "ac": "L" },
    "exploit_paths_active": true,
    "force_refresh_on_last_rebuild": false
  },

  "metrics": {
    "nodes": 67,
    "edges": 88,
    "unique_cves": 32,
    "trivy_vuln_count": 189,
    "crossings_raw": 32,
    "crossings_normalized": 0.9909,
    "crossings_per_edge": 0.3636,
    "drawing_area": 1523400.50,
    "area_per_node": 22737.32,
    "edge_length_cv": 0.7748
  }
}
```

When future metric work lands (per the sister plans), new keys appear under `metrics`. Schema version bumps only on **breaking** changes (renamed/removed keys), not additions.

### Reproducibility — `git_sha` instead of `metric_version`

Earlier drafts proposed a hand-maintained `metric_version` field that we'd bump whenever any metric algorithm changed. Replaced with `git_sha`: a build-time-injected commit hash of the code that produced the export. Two reasons:

1. **Automatic.** No human has to remember to bump a number after fixing a bug.
2. **Precise.** A `metric_version` of `"3"` doesn't tell you *which* commit of v3 you ran; the SHA does, and that commit is browsable on GitHub.

**Injection mechanism**: a `vite.config.ts` snippet that runs `git rev-parse HEAD` at build time and exposes the result as `import.meta.env.VITE_GIT_SHA`. The frontend reads it once on app load and includes it in every JSON export.

```typescript
// vite.config.ts (sketch)
import { execSync } from 'node:child_process';

const gitSha = execSync('git rev-parse HEAD').toString().trim();

export default defineConfig({
  define: {
    'import.meta.env.VITE_GIT_SHA': JSON.stringify(gitSha),
  },
  // ...
});
```

Dev-mode caveat: in dev, the SHA is of the working tree's `HEAD`, even if uncommitted changes exist. We **do not** detect dirty state in this iteration; document it as a known limitation. Anyone publishing a paper figure should run on a clean tree.

---

## What counts as "settings"?

Every user-controllable input that affects the displayed graph:

| Setting | Source | Notes |
|---------|--------|-------|
| Granularity sliders (per node type) | Backend `/api/config` | Already a snapshotted dict |
| `skip_layer_2` | Backend `/api/config` | Bool |
| Visibility toggles (which types are hidden) | Frontend state in `filter.ts` | Array of node-type strings |
| CVE merge mode | Frontend state in `cveMerge.ts` | `"none"` / `"prereqs"` / `"outcomes"` |
| Environment filter (UI / AC) | Frontend `<select>` values in DOM | Two single-letter strings |
| Exploit Paths active | Frontend state in `exploitPaths.ts` | Bool |
| Force-refresh used on last rebuild | Frontend `<input>` value | Bool — purely informational |
| Scan selection (which scans contributed) | Frontend `<select>` value + backend `/api/data/scans` | Used to populate `data_source.scans_in_current_graph` |

Layout choice (dagre / breadthfirst / cose / circle) is **also** captured as `settings.layout = "dagre"` — the metrics depend on it.

Things deliberately **not** captured (out of scope for reproducibility):
- Window size / zoom / pan (zoom-invariant by design; no effect on metrics)
- Light vs dark theme
- Selected nodes (analyst-session ephemera)

---

## Implementation

### Frontend — `frontend/js/features/metrics.ts`

Add a sibling to `metricsToCSV` / `downloadMetricsCSV`:

```typescript
export interface MetricsSnapshot {
  schema_version: 1;
  exported_at: string;       // ISO timestamp
  app_version: string;
  data_source: DataSourceSnapshot;
  settings: SettingsSnapshot;
  metrics: DrawingMetrics & Record<string, unknown>;
}

export function metricsToJSON(
  m: DrawingMetrics,
  context: MetricsCsvContext,
  settings: SettingsSnapshot,
  source: DataSourceSnapshot
): string;

export function downloadMetricsJSON(/* same args */): void;
```

The `SettingsSnapshot` and `DataSourceSnapshot` types live next to `DrawingMetrics`.

### Frontend — `frontend/js/features/settingsSnapshot.ts` (NEW)

Single function `gatherCurrentSettings(): SettingsSnapshot` that reads from each source. Lives in its own module so the metric module doesn't take a hard dependency on every UI state holder.

```typescript
export async function gatherCurrentSettings(): Promise<SettingsSnapshot> {
  // Reads from:
  //   - fetchConfig() (granularity + skip_layer_2)
  //   - getHiddenTypes() (visibility)
  //   - getMergeMode() (cveMerge)
  //   - DOM <select id="env-ui">, <select id="env-ac">
  //   - isExploitPathsActive() (exploitPaths)
  //   - DOM checkboxes (#force-refresh-checkbox)
  //   - getCurrentLayout() (layout)
  return { ... };
}
```

Async because `fetchConfig()` is async; the rest is synchronous DOM/state read.

### Frontend — `frontend/js/ui/statistics.ts`

Add a second button next to **📥 Export CSV**:

```
[ 📥 Export CSV ]   [ 📄 Export JSON ]
```

The JSON button calls `gatherCurrentSettings()` then `downloadMetricsJSON(...)`.

### App version

Read from `package.json`'s version field at build time. Vite supports `import.meta.env.VITE_APP_VERSION` if exposed via `vite.config.ts`. Alternative: hardcode for now and bump manually — acceptable since the field is informational.

### No backend changes

Everything's available via existing endpoints (`/api/config`, `/api/data/scans`) plus frontend state. No new backend work.

---

## UI Changes

### Statistics modal — Drawing Quality section

Current:
```
[ 🔍 Show debug overlay ]   [ 📥 Export CSV ]
```

After:
```
[ 🔍 Show debug overlay ]   [ 📥 Export CSV ]   [ 📄 Export JSON ]
```

Both export buttons capture the **current** modal data (computed when the modal was opened or last refreshed). Neither triggers a recompute.

---

## Tests

### `frontend/js/features/metrics.test.ts`

- `metricsToJSON` produces valid parseable JSON
- Schema version is 1
- All `DrawingMetrics` fields appear under the `metrics` key
- `metrics.trivy_vuln_count` is a number when context provides it, omitted (or `null`) otherwise
- Schema is stable: keys present in v1 are still present after adding a new metric (regression guard)

### `frontend/js/features/settingsSnapshot.test.ts` (NEW)

- `gatherCurrentSettings()` reads from all listed sources (mock each one)
- Returns sensible defaults when a source is unavailable (e.g., no exploit paths active → `false`)
- Visibility hidden array is sorted (deterministic for diffing across exports)

---

## Acceptance Criteria

- [ ] **📄 Export JSON** button exists in the Statistics modal next to Export CSV
- [ ] Clicking it downloads a `.json` file with the schema above
- [ ] Schema version, ISO timestamp, and app version are present
- [ ] `data_source.scans_in_current_graph` lists the scans that fed the rebuild (or all uploaded scans if none were specifically selected)
- [ ] All settings listed in the table above appear under `settings`
- [ ] Re-importing the JSON to set the app back to the same state would, in principle, reproduce the metrics (manual reproducibility — no auto-import in this plan)
- [ ] CSV export still works exactly as before
- [ ] Frontend test count: +5 to +8 tests
- [ ] Documentation updated in `Docs/_domains/StatisticsModal.md` listing the JSON schema

---

## Risks and Open Questions

| # | Risk | Mitigation |
|---|------|------------|
| 1 | `gatherCurrentSettings` async-creep — every export now has a network round-trip to `/api/config` | Cache config locally on modal open; refresh on rebuild |
| 2 | Schema versioning — if we add a metric and someone has v1 import code expecting the exact set | Document that additions are non-breaking; version bump only on rename/remove |
| 3 | App version coupling between this and `package.json` | Either build-time env var (vite) or accept a hardcoded constant with a TODO comment |
| 4 | Scan selection ambiguity — backend doesn't track which scans were in the *current* graph (only the full upload list) | Capture the scan IDs the user had selected at last rebuild; if none → "all" → list every uploaded scan with a flag `selection_was_implicit: true` |
| 5 | Settings drift between modal-open and JSON-download (user toggles something during the modal) | Snapshot settings at the same moment metrics were computed — store on `lastSettingsSnapshot` alongside `lastMetrics`, refresh together |

---

## Interaction with Sister Plans

This plan adds a **format**. The sister plans add **fields** under `metrics`. They don't conflict.

If both metric plans land before this one, this plan's `metrics` field grows automatically — no plan edits needed; just add the new fields to the JSON shape.

If this plan lands first, future metric additions just add new keys under `metrics`; the JSON schema remains v1.

Small enough to slot between phases of either sister plan, or to ship first as a foundation.

---

## Phasing

Single phase, executed in this order:

1. `vite.config.ts` SHA injection + a small helper exposing it in app code
2. `settingsSnapshot.ts` + tests
3. `metricsToJSON` + `downloadMetricsJSON`
4. UI button + wiring
5. Docs update + `StatisticsModal.md` schema reference

End state: every Statistics-modal session can produce a self-describing JSON snapshot.

---

## Files Affected

**New**:
- `frontend/js/features/settingsSnapshot.ts`
- `frontend/js/features/settingsSnapshot.test.ts`

**Modified**:
- `frontend/vite.config.ts` (git SHA injection)
- `frontend/js/features/metrics.ts` (JSON serializer + types)
- `frontend/js/features/metrics.test.ts`
- `frontend/js/ui/statistics.ts` (second export button, click handler)
- `frontend/index.html` (+1 button)
- `frontend/css/styles.css` (no change if reusing the CSV button styling)
- `Docs/_domains/StatisticsModal.md` (JSON schema doc)
