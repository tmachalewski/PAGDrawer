# Master Implementation Roadmap — Metrics & Export

**Created:** 2026-05-03-21-47
**Branch (proposed):** `feature/metrics-roadmap` (umbrella; sub-branches per phase)

---

## Daughter plans

This roadmap sequences three daughter plans living in `Docs/Plans/`:

1. **`JSON_Export_With_Settings.md`** — orthogonal export-format work. Adds 📄 Export JSON alongside the existing CSV, with a settings snapshot. ~6 h, single phase. No metric dependencies.
2. **`Debug_Overlay_Visualizations.md`** — 10 visualization-friendly metrics (M2, M3, M5, M8, M9, M19, M20, M21, M24, M25). ~22 h, 5 internal phases.
3. **`Paper_Evaluation_Metrics.md`** — 12 paper-priority metrics from `metric_proposals.md`'s "How I would prioritise" section (M1, M2, M11, M12, M14, M19, M20, M22, M24, M25, M26, M28). ~27 h, 4 internal phases.

The two metric plans **overlap on five metrics** (M2, M19, M20, M24, M25). Doing those once satisfies both. The roadmap below sequences phases so each metric is implemented exactly once.

A fourth document, **`metric_proposals.md`**, is the source-of-truth catalogue from which both metric plans were derived. It does not get touched by this roadmap.

---

## Source-of-truth files

| File in `Docs/Plans/` | Role |
|-----------------------|------|
| `metric_proposals.md` | Catalogue of 30 candidate metrics with formulas, complexity, sources, debug-overlay viability ratings, and paper-importance prioritisation |
| `JSON_Export_With_Settings.md` | Format work — JSON exporter + settings snapshot |
| `Debug_Overlay_Visualizations.md` | Implementation plan for 10 visualisable metrics + the new Debug Overlay modal |
| `Paper_Evaluation_Metrics.md` | Implementation plan for 12 paper-priority metrics; CSV-only where overlay isn't viable |
| `Master_Implementation_Roadmap.md` | **This file.** Single-pass ordered execution plan. |

---

## Overlap matrix

Rows = metric. Columns = which daughter plan covers it.

| Metric | Visualization plan | Paper plan | Notes |
|--------|:------------------:|:----------:|-------|
| M1  Stress | — | ✅ | Paper-only; CSV-only |
| M2  Crossing angle | ✅ | ✅ | Shared work |
| M3  Angular resolution | ✅ | — | Visual-only |
| M5  Edge length tinting | ✅ | — | Visual-only |
| M8  Bbox compactness | ✅ | — | Visual-only |
| M9  Aspect ratio | ✅ | — | Visual-only |
| M11 NP_k | — | ✅ | Paper-only; CSV-only |
| M12 Trustworthiness | — | ✅ | Paper-only; CSV-only |
| M14 Reachability preservation | — | ✅ | Paper-only; CSV-only; needs backend `/api/graph/full` |
| M19 Bridge contraction depth | ✅ | ✅ | Shared work; needs backend `chain_length` |
| M20 ECR | ✅ | ✅ | Shared work |
| M21 Group cardinality (generalised) | ✅ | — | Visual-only |
| M22 Attribute compression ratio | — | ✅ | Paper-only; CSV-only |
| M24 Column purity | ✅ | ✅ | Shared work |
| M25 Type-pair crossings | ✅ | ✅ | Shared work |
| M26 Edge-type distribution | — | ✅ | Paper-only; CSV-only |
| M28 Visual clutter | — | ✅ | Paper-only; CSV-only; needs corpus-level post-processing |

17 unique metrics in total; 5 shared between plans.

---

## Default sequencing — paper-essential first

Optimised for: getting the paper-essential metrics into the CSV as fast as possible, while minimising rework. JSON export comes first because it's small and makes everything downstream cleaner.

### Stage 0 — Foundation (~6 h)

**Daughter plan:** `JSON_Export_With_Settings.md` (single phase)

- Add `📄 Export JSON` button next to existing CSV button
- New `gatherCurrentSettings()` helper
- New `metricsToJSON` / `downloadMetricsJSON` in `metrics.ts`
- Tests + docs

End state: every export is reproducible. Future metric additions land in both CSV and JSON automatically.

---

### Stage 1 — Quick wins + modal scaffold (~3 h)

**Daughter plan:** `Debug_Overlay_Visualizations.md` Phase 1

- M9 (aspect ratio label on bbox)
- M21 (group cardinality badges, generalised across compound types)
- New Debug Overlay Settings modal (per-overlay checkboxes for the existing 4 + future toggles)

End state: the modal exists; existing 4 overlays are individually toggleable; M9 and M21 are in CSV + visible.

---

### Stage 2 — Crossings refinement (~4 h, shared between plans)

**Daughter plans:** `Debug_Overlay_Visualizations.md` Phase 2 + `Paper_Evaluation_Metrics.md` Phase 1 partial

- M2 (crossing angle math + dot coloring)
- M25 (type-pair crossings + dot coloring)
- Radio group "Crossings color by" in Debug Overlay modal

End state: both M2 and M25 are in CSV (paper benefit) and visualised (overlay benefit). One implementation, two plan checkboxes ticked.

---

### Stage 3 — Paper-essential exclusives (~8 h)

**Daughter plan:** `Paper_Evaluation_Metrics.md` Phase 1 (remaining)

- M1 Stress (~5 h, incl. APSP helper that M11 / M12 will reuse later)
- M14 Reachability preservation (~3 h, incl. backend `/api/graph/full` endpoint)

End state: the most-cited GD metric (M1) and the proof-validation metric (M14) are in CSV. **Body-of-paper evaluation table is now complete (M1, M2, M14, M20, M25).**

> Wait — M20 hasn't shipped yet at this stage. Re-ordering: bump M20 ahead. See revised order in Stage 4.

---

### Stage 4 — Bridges and merges (~6 h, shared between plans)

**Daughter plans:** `Debug_Overlay_Visualizations.md` Phase 3 + `Paper_Evaluation_Metrics.md` Phase 1 final + Phase 2 partial

- Backend wiring: `chain_length` on bridge edges (`src/graph/builder.py` + `src/viz/app.py` + tests)
- M19 (bridge contraction depth labels + scalars)
- M20 (ECR computation + label addition)

End state: both reduction mechanisms are visually quantified. **Body-of-paper set is now genuinely complete: M1, M2, M14, M20, M25 all in CSV.** M19, M22, M24 from the appendix set are next.

---

### Stage 5 — Paper appendix essentials (~3.5 h)

**Daughter plan:** `Paper_Evaluation_Metrics.md` Phase 2 (remaining after M19)

- M22 Attribute compression ratio (CSV-only, ~1.5 h)
- M26 Edge-type distribution (CSV-only, wide-string format, ~1 h)
- M24 Column purity — already from Stage 6 below; pulled forward if it makes sense

End state: 3 of the 4 Paper Phase 2 metrics done.

---

### Stage 6 — Layout diagnostics (~5.5 h, shared between plans for M24)

**Daughter plans:** `Debug_Overlay_Visualizations.md` Phase 4 + `Paper_Evaluation_Metrics.md` Phase 2 final

- M3 Angular resolution arcs (~4 h, visual-only)
- M24 Column purity (~1.5 h, shared — halo overlay + CSV)

End state: layout problems pop visually; M24 closes out Paper Phase 2.

---

### Stage 7 — Topology preservation (~5 h, paper-only)

**Daughter plan:** `Paper_Evaluation_Metrics.md` Phase 3

- M11 NP_k (~3.5 h, reuses APSP from M1)
- M12 Trustworthiness (~1.5 h, reuses APSP and ranks)

End state: dimension-reduction-style story is complete in CSV.

---

### Stage 8 — Composite scalar (~2 h + post-processing)

**Daughter plan:** `Paper_Evaluation_Metrics.md` Phase 4

- M28 Visual clutter (~2 h frontend; computes raw components per snapshot)
- New `scripts/compute_clutter_score.py` (~50 LOC) that reads exported JSONs from a corpus and adds the corpus-normalised `clutter_score` field

End state: every paper-priority metric is in CSV + JSON. **Paper plan complete.**

---

### Stage 9 — Surface treatments (~4 h, visual-only)

**Daughter plan:** `Debug_Overlay_Visualizations.md` Phase 5

- M5 Edge length deviation tint (~2 h; defer if hard)
- M8 Bbox compactness shading (~2 h)

End state: every visualisation-friendly metric is implemented. **Visualisation plan complete.**

---

## Stage table

| Stage | What | Daughter plans | Hours | Cumulative |
|-------|------|----------------|------:|-----------:|
| 0 | JSON export + settings snapshot | JSON_Export_With_Settings | 6 | 6 |
| 1 | Modal scaffold + M9 + M21 | Debug_Overlay (P1) | 3 | 9 |
| 2 | M2 + M25 (crossings refinement) | Debug_Overlay (P2) + Paper (P1) | 4 | 13 |
| 3 | M1 + M14 (paper-essential exclusives) | Paper (P1) | 8 | 21 |
| 4 | M19 + M20 (bridges + merges, with backend) | Debug_Overlay (P3) + Paper (P1/P2) | 6 | 27 |
| 5 | M22 + M26 (CSV-only paper appendix) | Paper (P2) | 3.5 | 30.5 |
| 6 | M3 + M24 (layout diagnostics) | Debug_Overlay (P4) + Paper (P2) | 5.5 | 36 |
| 7 | M11 + M12 (topology preservation) | Paper (P3) | 5 | 41 |
| 8 | M28 (composite + post-processing) | Paper (P4) | 2 | 43 |
| 9 | M5 + M8 (surface treatments) | Debug_Overlay (P5) | 4 | 47 |

**Total: ~47 h.** Sum of daughter plans without overlap dedup would be 6 + 22 + 27 = 55 h; the roadmap saves ~8 h by sharing the 5 overlapping metrics.

Body-of-paper set (M1, M2, M14, M20, M25) is complete after **Stage 4 (~27 h)**.

Paper plan complete after **Stage 8 (~43 h)**.

Visualisation plan complete after **Stage 9 (~47 h)**.

---

## Alternative orderings

The default above optimises for "paper-essential CSV columns first." If you want to optimise for something else:

### "Maximize live debug experience first"

Run all of `Debug_Overlay_Visualizations.md` before any paper-only metrics. Stage order:

0 → Visualisation Phases 1–5 (~22 h) → Paper-only metrics (M1, M11, M12, M14, M22, M26, M28; ~17.5 h)

Result: visualisation plan done at ~28 h; paper plan done at ~47 h.

### "Cheapest first (build momentum)"

Sort all stages by individual hour cost ascending:

JSON (6) → M21 (1) → M22 (1.5) → M24 (1.5) → M9 (≈ free, in M9-M21 stage) → M26 (1) → M2+M25 (4) → M28 (2) → M5 (2) → M8 (2) → M3 (4) → M11 (3.5) → M12 (1.5) → M19 (3) → M20 (3) → M14 (3) → M1 (5)

Quickest visible progress; least suited to a paper deadline.

### "Backend-first"

Bundle all backend work (M14 endpoint + M19 chain_length) into Stage 1, before any frontend metric work. Buys you a stable backend contract before iterating on the frontend.

---

## Cross-cutting concerns

These apply across stages and should be handled consistently throughout:

| Concern | How |
|---------|-----|
| **Test count growth** | Backend: 381 → ~395 (M14 endpoint, M19 chain_length). Frontend: 159 → ~210. Each stage adds ~5–15 tests. |
| **CSV column ordering** | Append new columns at the end of the existing header. Document the order in `Docs/_domains/StatisticsModal.md` and `Docs/_domains/DrawingQualityMetrics.md`. |
| **JSON schema versioning** | Stay at v1 throughout — additions are non-breaking per the JSON plan. Bump to v2 only on rename/remove. |
| **Documentation** | After each stage, update `Docs/_domains/StatisticsModal.md` and `Docs/_domains/DrawingQualityMetrics.md`. Daily note per stage: `Docs/_dailyNotes/YYYY-MM-DD-HH-mm-Stage-N-...md`. |
| **Branching** | One umbrella branch `feature/metrics-roadmap`; sub-branches per stage merging back into umbrella; umbrella merges to `main` after the paper plan completes (Stage 8) — visualisation-only Stage 9 can ship later. |
| **Per-stage acceptance** | Each stage delivers a green test suite, an updated CSV column set, and an updated JSON schema. No half-shipped stages. |

---

## What this roadmap does NOT change

- The daughter plans remain authoritative for per-metric implementation detail. This file only sequences them.
- `metric_proposals.md` is unchanged; it stays the catalogue.
- The 13 ❌ metrics from `metric_proposals.md` remain out of scope (per both metric plans' "Out of Scope" sections).
- The 7 ⚠️ metrics that were dropped from both plans (M1 visual variant, M4, M7, M11/M12 interactive overlays, M13, M27) remain future work.

---

## Phasing decision points

After each stage, the project should review:

1. **Is the paper deadline still on track?** If not, drop later stages from scope; the body-of-paper set is complete after Stage 4.
2. **Are visualisations adding the value we expected?** If overlays clutter rather than clarify, defer Stage 9.
3. **Do new metrics correlate with each other?** If yes, the paper might collapse some columns; if no, they all stay.
4. **Has the CSV become unwieldy?** Currently 10 columns; after full roadmap ≈ 25. If reviewers complain, a "summary CSV" with just the body-of-paper metrics could be a separate small plan.

---

## Files that will be touched across the roadmap

Aggregated from the three daughter plans:

**Frontend modified throughout**:
- `frontend/js/features/metrics.ts` (computation + types for 17 metrics)
- `frontend/js/features/metrics.test.ts`
- `frontend/js/ui/statistics.ts` (table rows + buttons)
- `frontend/js/ui/debugOverlay.ts` (NEW — extracted overlay logic + new toggles)
- `frontend/js/features/settingsSnapshot.ts` (NEW — Stage 0)
- `frontend/index.html`, `frontend/css/styles.css`
- `frontend/js/services/api.ts` (M14 full-graph endpoint)
- `frontend/js/config/constants.ts` (new pseudo-element styles for M3, M24, etc.)

**Backend modified at Stages 3–4**:
- `src/graph/builder.py` (M19 chain_length recording)
- `src/viz/app.py` (M14 `/api/graph/full` endpoint, M19 chain_length pass-through)
- `tests/test_builder.py`, `tests/test_api_endpoints.py`

**New utility script (Stage 8)**:
- `scripts/compute_clutter_score.py`

**Documentation (continuously)**:
- `Docs/_domains/StatisticsModal.md`
- `Docs/_domains/DrawingQualityMetrics.md`
- `Docs/_dailyNotes/...` (per stage)
- `Docs/_projectStatus/...` (after Stage 4 and Stage 8 — version bump opportunities)
