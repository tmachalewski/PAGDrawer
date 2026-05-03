# 2026-05-03 - Bug Fixes (Exploit Paths × Bridge / Merge × Hidden) + Metric Additions

## Overview

Four commits worth of work that came out of using the app on real Trivy scans (alpine, nginx, postgres, redis, ubuntu, etc.). Two visibility bugs surfaced when combining filters; two new CSV columns make the Drawing Quality export more useful for the paper.

---

## 1. Fix: bridge nodes preserved in Exploit Paths view (`95b14ca`)

**Symptom**: with `skip_layer_2=True` and Exploit Paths active, the `INSIDE_NETWORK` bridge disappeared.

**Cause**: the Exploit Paths filter runs a backward BFS from `EX:Y` terminals via `incomers()`. In 2-layer mode the bridge sits between L1 and L2 and is naturally on a backward path to L2 terminals. In skip_layer_2 mode the bridge has only *outgoing* edges (it's downstream of L1 terminals); the backward walk never reaches it and it gets `exploit-hidden`.

**Fix**: `frontend/js/features/exploitPaths.ts` — always include `[?is_phase_separator]` nodes in `nodesOnPath`, plus the edges connecting them to already-visible terminals. Mirrors the existing always-include logic for `ATTACKER_BOX` / `ATTACKER`.

Test: added one mock-level test verifying `cy.nodes('[?is_phase_separator]')` is queried on every toggle.

---

## 2. Fix: exclude exploit-hidden CVEs from merge groups (`da04786`)

**Symptom**: when Exploit Paths was active and the user then applied CVE merge by outcomes, an empty "no VCs" compound appeared at (0, 0) instead of in the proper column.

**Cause**: `applyMerge()` selected every CVE node via `cy.nodes('[type="CVE"]')` regardless of the `exploit-hidden` class. Exploit-hidden CVEs (which by construction reach no `EX:Y`) ended up in the empty-outcomes group; the resulting compound had every child with `display: none`, dagre couldn't position it, and it stranded at the origin.

**Fix**: `frontend/js/features/cveMerge.ts` — filter out `hasClass('exploit-hidden')` before grouping:

```typescript
const cveNodes = cy.nodes('[type="CVE"]').filter(n => !n.hasClass('exploit-hidden'));
```

Test: added a case where one of three same-prereqs CVEs is exploit-hidden; the resulting group has 2 members, not 3.

Test infrastructure tweak: the mock collection helper in `cveMerge.test.ts` now exposes `.filter` (returning another mock collection) and each mock node has a default `hasClass` returning `false`.

---

## 3. Metric: area per node (`38db337`)

`drawing_area / |V|`. Easier to explain to paper readers than raw drawing area: it normalizes for graph size, so progressive reduction steps can be compared even though `|V|` is changing.

| Direction | Meaning |
|-----------|---------|
| Lower | Denser drawing |
| Higher | Sparser, more whitespace per node |

- New `areaPerNode` field on `DrawingMetrics`
- New row in the Statistics modal: `Area per node (lower = denser)`
- New `area_per_node` column in CSV export

---

## 4. Metric: unique CVE count + Trivy vulnerability total (`8747292`)

Two new CSV columns and two new modal rows so paper readers can see graph-vulnerability counts alongside drawing-aesthetics numbers.

| Column | What it is | Source |
|--------|-----------|--------|
| `unique_cves` | distinct base CVE IDs in the live graph | computed sync from CVE node IDs (strip `:dN` and `@...` context suffixes) |
| `trivy_vuln_count` | sum of Trivy-reported per-package vulnerability entries across all uploaded scans | `/api/data/scans` returns `vuln_count` per scan; we sum |

The `trivy_vuln_count` is **across all uploaded scans**, not just the ones in the current rebuild. The backend doesn't currently track which scans contributed to the live graph. Mentioned in the CSV column comment for honesty; could be tightened later by exposing `current_scan_ids` from the API.

`metricsToCSV(m, context)` now takes an optional `MetricsCsvContext` so callers can inject backend-only counts. `statistics.ts` fetches the scan list when the modal opens, stores the sum in `lastTrivyVulnCount`, and passes it via context to `downloadMetricsCSV`.

---

## 5. Test count

- Backend: unchanged (no backend changes in this batch)
- Frontend: 156 → 159 tests (+1 exploit-paths bridge test, +1 merge exploit-hidden filter test, +1 metrics CSV test for new columns)

---

## 6. Files changed

| File | Change |
|------|--------|
| `frontend/js/features/exploitPaths.ts` | Always include phase-separator (bridge) nodes |
| `frontend/js/features/exploitPaths.test.ts` | New test for bridge inclusion |
| `frontend/js/features/cveMerge.ts` | Filter exploit-hidden CVEs before grouping |
| `frontend/js/features/cveMerge.test.ts` | Mock now supports `.filter` and `hasClass`; new test |
| `frontend/js/features/metrics.ts` | `areaPerNode`, `uniqueCves`, `MetricsCsvContext`, `metricsToCSV` extended |
| `frontend/js/features/metrics.test.ts` | Updated CSV test for the new columns |
| `frontend/js/ui/statistics.ts` | Display new rows; fetch scan list; pass context to CSV |
