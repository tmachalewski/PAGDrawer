# Master Implementation Roadmap — Metrics & Export

**Created:** 2026-05-03-21-47
**Branch (proposed):** `feature/metrics-roadmap` (umbrella; sub-branches per phase)

---

## Daughter plans

This roadmap sequences three daughter plans living in `Docs/Plans/`:

1. **`JSON_Export_With_Settings.md`** — orthogonal export-format work. Adds 📄 Export JSON alongside the existing CSV, with a settings snapshot and a build-time-injected `git_sha`. Single phase. No metric dependencies.
2. **`Debug_Overlay_Visualizations.md`** — 10 visualization-friendly metrics (M2, M3, M5, M8, M9, M19, M20, M21, M24, M25). 5 internal phases.
3. **`Paper_Evaluation_Metrics.md`** — 10 paper-priority metrics from `metric_proposals.md`'s "How I would prioritise" section, **minus M14 and M28 (deferred)**: M1, M2, M11, M12, M19, M20, M22, M24, M25, M26. 3 internal phases.

The two metric plans **overlap on five metrics** (M2, M19, M20, M24, M25). Doing those once satisfies both. The roadmap below sequences phases so each metric is implemented exactly once.

A fourth document, **`metric_proposals.md`**, is the source-of-truth catalogue from which both metric plans were derived. It does not get touched by this roadmap.

---

## Source-of-truth files

| File in `Docs/Plans/` | Role |
|-----------------------|------|
| `metric_proposals.md` | Catalogue of 30 candidate metrics with formulas, complexity, sources, debug-overlay viability ratings, and paper-importance prioritisation |
| `JSON_Export_With_Settings.md` | Format work — JSON exporter + settings snapshot + git SHA |
| `Debug_Overlay_Visualizations.md` | Implementation plan for 10 visualisable metrics + the new Debug Overlay modal (with presets) |
| `Paper_Evaluation_Metrics.md` | Implementation plan for 10 paper-priority metrics; export-only where overlay isn't viable |
| `Master_Implementation_Roadmap.md` | **This file.** Single-pass ordered execution plan. |

---

## Overlap matrix

Rows = metric. Columns = which daughter plan covers it.

| Metric | Visualization plan | Paper plan | Notes |
|--------|:------------------:|:----------:|-------|
| M1  Stress | — | ✅ | Paper-only; export-only |
| M2  Crossing angle | ✅ | ✅ | Shared work |
| M3  Angular resolution | ✅ | — | Visual-only |
| M5  Edge length tinting | ✅ | — | Visual-only |
| M8  Bbox compactness | ✅ | — | Visual-only |
| M9  Aspect ratio | ✅ | — | Visual-only |
| M11 NP_k | — | ✅ | Paper-only; export-only |
| M12 Trustworthiness | — | ✅ | Paper-only; export-only |
| M19 Bridge contraction depth | ✅ | ✅ | Shared work; needs backend `chain_length` |
| M20 ECR | ✅ | ✅ | Shared work |
| M21 Group cardinality (generalised) | ✅ | — | Visual-only |
| M22 Attribute compression ratio | — | ✅ | Paper-only; export-only; needs `mergeKeys.ts` extraction |
| M24 Column purity | ✅ | ✅ | Shared work |
| M25 Type-pair crossings | ✅ | ✅ | Shared work |
| M26 Edge-type distribution | — | ✅ | Paper-only; export-only; one CSV column per edge type |

15 unique metrics; 5 shared between plans. (M14 and M28 are deferred per the Paper plan; they appear on neither side.)

---

## Default sequencing — paper-essential first

Optimised for: getting the paper-essential metrics into the CSV as fast as possible, while minimising rework. JSON export comes first because it makes downstream exports cleaner (and gives every metric the settings-snapshot capture for free).

### Stage 0 — Foundation

**Daughter plan:** `JSON_Export_With_Settings.md` (single phase)

- Vite-injected `git_sha` build constant
- New `gatherCurrentSettings()` helper
- New `metricsToJSON` / `downloadMetricsJSON` in `metrics.ts`
- Add 📄 Export JSON button next to existing CSV button
- Tests + docs

End state: every export is reproducible. Future metric additions land in both CSV and JSON automatically.

---

### Stage 1 — Foundation: extraction + quick wins

**Daughter plan:** `Debug_Overlay_Visualizations.md` Phase 1

- **Extract** the existing 4 overlays from `statistics.ts` into a new `debugOverlay.ts` module (see "Existing-Overlay Extraction" in the Visualization plan)
- New Debug Overlay Settings modal scaffold + preset row + per-overlay checkbox grid
- Per-overlay state machine + localStorage persistence (`debugOverlayState_v1`)
- M9 (aspect ratio label on bbox)
- M21 (group cardinality badges, generalised across compound types)

End state: the modal exists; existing 4 overlays are individually toggleable; presets work; M9 and M21 are in CSV + visible.

---

### Stage 2 — Crossings refinement (shared between plans)

**Daughter plans:** `Debug_Overlay_Visualizations.md` Phase 2 + `Paper_Evaluation_Metrics.md` Phase 1 partial

- M2 (crossing angle math + dot coloring)
- M25 (type-pair crossings + dot coloring)
- Radio group "Crossings color by" in Debug Overlay modal

End state: both M2 and M25 are in CSV (paper benefit) and visualised (overlay benefit). One implementation, two plan checkboxes ticked.

---

### Stage 3 — Stress (paper-essential exclusive)

**Daughter plan:** `Paper_Evaluation_Metrics.md` Phase 1 partial

- M1 Stress, including an APSP helper that M11 / M12 will reuse later

End state: M1 in the CSV. Body-of-paper set is now M1 + M2 + M25 in CSV; M20 ships next.

---

### Stage 4 — Bridges and merges (shared between plans)

**Daughter plans:** `Debug_Overlay_Visualizations.md` Phase 3 + `Paper_Evaluation_Metrics.md` Phase 1 final + Phase 2 partial

- Backend wiring: `chain_length` on bridge edges (`src/graph/builder.py` + `src/viz/app.py` + tests)
- M19 (bridge contraction depth labels + scalars)
- M20 (ECR computation + label addition)

End state: both reduction mechanisms are visually quantified. **Body-of-paper set is now complete in CSV: M1, M2, M20, M25.** M19 from the appendix set is also done as a side effect.

---

### Stage 5 — Paper appendix essentials (export-only)

**Daughter plan:** `Paper_Evaluation_Metrics.md` Phase 2 (remaining after M19)

- M22 Attribute compression ratio (export-only) — includes extracting `mergeKeys.ts` from `cveMerge.ts` so M22 can use the merge key functions
- M26 Edge-type distribution (export-only; **one CSV column per edge type**, single nested object in JSON)

End state: 2 of the 3 remaining Paper Phase 2 metrics done. M24 is in Stage 6 (shared with overlay plan).

---

### Stage 6 — Layout diagnostics (M24 shared with paper plan)

**Daughter plans:** `Debug_Overlay_Visualizations.md` Phase 4 + `Paper_Evaluation_Metrics.md` Phase 2 final

- M3 Angular resolution arcs (visual-only)
- M24 Column purity (shared — halo overlay + CSV)

End state: layout problems pop visually; M24 closes out Paper Phase 2.

---

### Stage 7 — Topology preservation (paper-only)

**Daughter plan:** `Paper_Evaluation_Metrics.md` Phase 3

- M11 NP_k (reuses APSP from M1)
- M12 Trustworthiness (reuses APSP and ranks from M11)

End state: dimension-reduction-style story is complete in CSV. **Paper plan complete.**

---

### Stage 8 — Surface treatments (visual-only)

**Daughter plan:** `Debug_Overlay_Visualizations.md` Phase 5

- M5 Edge length deviation tint (defer if hard)
- M8 Bbox compactness shading

End state: every visualisation-friendly metric is implemented. **Visualisation plan complete.**

---

## Stage table

| Stage | What | Daughter plans |
|-------|------|----------------|
| 0 | JSON export + settings snapshot + git SHA | JSON_Export_With_Settings |
| 1 | Existing-overlay extraction + modal scaffold + presets + M9 + M21 | Debug_Overlay (P1) |
| 2 | M2 + M25 (crossings refinement) | Debug_Overlay (P2) + Paper (P1) |
| 3 | M1 (stress, with APSP helper) | Paper (P1) |
| 4 | M19 + M20 (bridges + merges, with backend) | Debug_Overlay (P3) + Paper (P1/P2) |
| 5 | M22 + M26 (export-only paper appendix; includes `mergeKeys.ts` extraction) | Paper (P2) |
| 6 | M3 + M24 (layout diagnostics) | Debug_Overlay (P4) + Paper (P2) |
| 7 | M11 + M12 (topology preservation) | Paper (P3) |
| 8 | M5 + M8 (surface treatments) | Debug_Overlay (P5) |

**Body-of-paper set complete after Stage 4** (M1, M2, M20, M25 in CSV).
**Paper plan complete after Stage 7.**
**Visualization plan complete after Stage 8.**

---

## Alternative orderings

The default above optimises for "paper-essential CSV columns first." If you want to optimise for something else:

### "Maximize live debug experience first"

Run all of `Debug_Overlay_Visualizations.md` before any paper-only metrics. Stage order:

0 → Visualisation Phases 1–5 → Paper-only metrics (M1, M11, M12, M22, M26)

Result: visualisation plan done before paper plan starts.

### "Cheapest first (build momentum)"

Sort by individual metric size, smallest first: JSON → M21 → M22 → M24 → M9 → M26 → M2+M25 → M5 → M8 → M3 → M11+M12 → M19+M20 → M1.

Quickest visible progress; least suited to a paper deadline.

### "Backend-first"

Bundle the only backend work (M19 chain_length) into Stage 1, before any frontend metric work. Buys you a stable backend contract before iterating on the frontend.

---

## Cross-cutting concerns

These apply across stages and should be handled consistently throughout:

| Concern | How |
|---------|-----|
| **Test count growth** | Backend grows by a few tests (M19 chain_length). Frontend grows substantially with each stage. Each stage adds tests for its metrics. |
| **CSV column ordering** | Append new columns at the end of the existing header. Document the order in `Docs/_domains/StatisticsModal.md` and `Docs/_domains/DrawingQualityMetrics.md`. |
| **JSON schema versioning** | Stay at v1 throughout — additions are non-breaking per the JSON plan. Bump to v2 only on rename/remove. |
| **Reproducibility** | Every JSON export carries the `git_sha` of the code that produced it. No manual `metric_version` bumping required. |
| **M26 column set** | One CSV column per edge type, sourced from the edge-type enum. JSON export carries a single nested `edge_type_distribution` object. A regression test asserts the CSV column set stays in sync with the enum. |
| **Extraction prerequisite** | Stage 1 starts by moving the existing 4 overlays into the new `debugOverlay.ts` module before adding any new ones. Every subsequent stage's overlay work assumes the module exists. |
| **Documentation** | After each stage, update `Docs/_domains/StatisticsModal.md` and `Docs/_domains/DrawingQualityMetrics.md`. Daily note per stage: `Docs/_dailyNotes/YYYY-MM-DD-HH-mm-Stage-N-...md`. |
| **Branching** | One umbrella branch `feature/metrics-roadmap` off `main`; each stage gets its own sub-branch off the umbrella, named `feature/metrics-roadmap/<stage-slug>` (e.g. `feature/metrics-roadmap/json-export`, `feature/metrics-roadmap/overlay-foundation`, `feature/metrics-roadmap/crossings`, `feature/metrics-roadmap/stress`, `feature/metrics-roadmap/bridges-and-merges`, `feature/metrics-roadmap/paper-appendix`, `feature/metrics-roadmap/layout-diagnostics`, `feature/metrics-roadmap/topology-preservation`). Each sub-branch merges back into the umbrella once its acceptance criteria pass. Umbrella merges to `main` after Stage 7 (Paper plan complete). Stage 8 (visual-only surface treatments) ships on a separate post-umbrella branch `feature/visualization-surface` off `main` so it doesn't block the paper-essential merge. The daughter-plan-named branches (`feature/json-export`, `feature/paper-metrics`, `feature/debug-overlays`) listed in the daughter plans are aliases for the corresponding stage sub-branches above — kept in the docs for cross-reference. |
| **Per-stage acceptance** | Each stage delivers a green test suite, an updated CSV column set, and an updated JSON schema. No half-shipped stages. |

---

## What this roadmap does NOT change

- The daughter plans remain authoritative for per-metric implementation detail. This file only sequences them.
- `metric_proposals.md` is unchanged; it stays the catalogue.
- The 13 ❌ metrics from `metric_proposals.md` remain out of scope (per both metric plans' "Out of Scope" sections).
- M14 (reachability preservation) and M28 (visual clutter) — both originally in the Paper plan — are deferred. The Paper plan's "Deferred for now" section explains why.
- The 7 ⚠️ metrics that were dropped from the Visualization plan (M1 visual variant, M4, M7, M11/M12 interactive overlays, M13, M27) remain future work.

---

## Phasing decision points

After each stage, the project should review:

1. **Is the paper deadline still on track?** If not, drop later stages from scope; the body-of-paper set is complete after Stage 4.
2. **Are visualisations adding the value we expected?** If overlays clutter rather than clarify, defer Stage 8.
3. **Do new metrics correlate with each other?** If yes, the paper might collapse some columns; if no, they all stay.
4. **Has the CSV become unwieldy?** Currently 10 columns; after full roadmap will have grown substantially. If reviewers complain, a "summary CSV" with just the body-of-paper metrics could be a separate small plan.
5. **Should M14 / M28 be revived?** Deferred per the Paper plan. Reconsider when the paper draft is read by an outside reviewer who flags the gap.

---

## Files that will be touched across the roadmap

Aggregated from the three daughter plans:

**Frontend modified throughout**:
- `frontend/js/features/metrics.ts` (computation + types for 15 metrics)
- `frontend/js/features/metrics.test.ts`
- `frontend/js/ui/statistics.ts` (table rows + JSON button)
- `frontend/js/ui/debugOverlay.ts` (NEW — extracted overlay logic + new toggles + presets)
- `frontend/js/features/settingsSnapshot.ts` (NEW — Stage 0)
- `frontend/js/features/mergeKeys.ts` (NEW — Stage 5; extracted from `cveMerge.ts`)
- `frontend/index.html`, `frontend/css/styles.css`
- `frontend/vite.config.ts` (Stage 0 — git SHA injection)
- `frontend/js/config/constants.ts` (new pseudo-element styles for M3, M24, etc.)

**Backend modified at Stage 4**:
- `src/graph/builder.py` (M19 chain_length recording)
- `src/viz/app.py` (M19 chain_length pass-through)
- `tests/test_builder.py` (M19 unit test)

**Documentation (continuously)**:
- `Docs/_domains/StatisticsModal.md`
- `Docs/_domains/DrawingQualityMetrics.md`
- `Docs/_dailyNotes/...` (per stage)
- `Docs/_projectStatus/...` (after Stage 4 and Stage 7 — version bump opportunities)
