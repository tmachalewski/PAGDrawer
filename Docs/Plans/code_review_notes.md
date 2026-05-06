# Review notes: `MetricsPaperReference.md` and the two nginx scenarios

A review of the paper-implementation liaison document and the two preliminary test runs (Hide CWE+TI vs Hide CPE+CWE+TI). Numbers come from ten JSON exports captured 5 May 2026 in a single session, build `1.0.0` commit `00f46fc`. This is not a finished paper artefact, it is a punch list of changes to consider before the GD 2026 deadline (paper deadline 13 May, abstract 6 May).

---

## 1. What I think about `MetricsPaperReference.md`

This is exactly the kind of paper-implementation liaison document I was recommending earlier, only built more carefully than most teams manage. It maps each metric to its formula, its TypeScript implementation, its expected behaviour under each reduction mechanism, the caveats, and the paper-ready pseudocode side by side. A reviewer who wants to verify can open `frontend/js/features/metrics.ts` and see that `computeStressFromAPSP` does what the section's formula says it does.

### What is strong

**Section 4 (caveats) is mature.** Eleven explicitly named limitations, each numbered, each with a mitigation note. Caveat 4.3 (`stress_unreachable_pairs` inflates after merge) is exactly the kind of issue a hostile reviewer looks for to attack, and you already have the answer ready. Caveat 4.11 (chain_length is lost when merge runs before hide) is the most honest thing you could say in a paper: "this works when applied in the recommended order." Caveat 4.13 (bridge_edge_proportion has an unstable denominator after merge) protects you from the trap of someone comparing this value across steps and concluding "suddenly everything is bridges."

**One-to-one pseudocode with the TypeScript.** The worked example for chain_length in section 5.7 (CVE → CWE → TI → VC, two hide steps, final value 2) is gold for reviewers. Each formula has a file and function reference. A reviewer can reproduce the metric from the source without context-switching to the implementation.

**Symmetrised stress on a directed graph.** The choice of `min(d_{i→j}, d_{j→i})` is a defensive decision that you have honestly documented. The alternative ("we report strict-directed stress, ~50% of pairs are unreachable") would be unreadable in any layered DAG, so this is a pragmatic choice worth defending in front of reviewers.

**JSON schema with `git_sha` + `app_version` + settings snapshot + `data_source`.** This is provenance metadata of the kind rigorous ML papers cite (model cards, datasheets). A senior reviewer will appreciate that any figure in the paper can be reproduced from the same commit. The note that "SHA reflects HEAD even with uncommitted changes" is honest, but consider enforcing a clean tree on figure export (banner in the UI when `git status --porcelain` is non-empty).

### Where I have reservations

**Stages 5-7 of the metrics roadmap deferred.** Section 1 mentions that *Stages 5-7 of the metrics roadmap will add M3, M11, M12, M22, M24, M26.* For the short paper (250 lines) this is fine, but for the long paper (500 lines) I would push to land M22 (Attribute Compression Ratio) before the deadline. ACR has the property that it *predicts* how much the merge step will reduce, which lets you add an "expected reduction" column next to the "actual reduction" column. The reader sees that theory matches experiment for cheap, and reviewers like that pattern.

**The microseconds claim contradicts the data.** Caveat 4.9 says *PAGDrawer's typical |E| is 100s, not thousands, brute-force is microseconds.* Your nginx Step 1 has |E| = 5675 and `C_raw` = 5,252,118. Brute-force segment intersection is ~16M comparisons. Even if it runs in ~30 ms in TypeScript, that is not "microseconds." Either rephrase or include a concrete timing measurement for the largest scan in the corpus.

> **Resolution (2026-05-06).** Rephrased the timing claims in three docs (MetricsPaperReference.md § 4.9, DrawingQualityMetrics.md APSP paragraph, StressMetric.md complexity table) to reflect honest order-of-magnitude estimates anchored on the actual nginx baseline ($|V| \approx 830$, $|E| \approx 5{,}675$): tens of milliseconds at baseline, sub-millisecond after Step 2. Concrete `performance.now()` medians for the five pipeline steps will be measured during paper writing and inserted at that point — TODO note left at `MetricsPaperReference.md § 4.9`.

**Singleton fraction as noise.** Keeping `compound_singleton_fraction` "at 0 in normal operation" is fine as a regression sentinel, but do not report this column in the paper body. A reviewer reads "100% of groups have >1 element" and thinks "well, how could it be otherwise?" Keep the metric in JSON for diagnostics, but in the body and appendix only `compound_groups_count` and `compound_largest_group_size`.

---

## 2. Comparison of the two nginx scenarios

I read all ten JSON exports. Both runs share the first two steps (baseline plus granularity slider) and diverge at Step 3.

> **Five-step pipeline.** In both scenarios: (1) baseline with default sliders, (2) granularity (VC slider from TI to HOST), (3) hide chosen layers, (4) merge by outcomes, (5) exploit paths only. The difference: scenario 1 hides CWE+TI (keeps CPE), scenario 2 hides CPE+CWE+TI together.

### Final-state comparison

| Metric after full pipeline | Hide CWE+TI (CPE kept) | Hide CPE+CWE+TI |
|---|---:|---:|
| N (nodes) | 103 | **78** |
| E (edges) | 85 | **27** |
| `C_raw` (crossings) | 272 | **10** |
| `C/E` | 3.20 | **0.37** |
| Mean crossing angle | 24° | **34.2°** |
| RAC (right-angle ratio) | 0.051 | **0.10** |
| ECR_w | 5.64 | **24.93** |
| top_pair | HAS_VULN × HAS_VULN | BRIDGE × BRIDGE |

Every key metric is better in the hide-CPE+CWE+TI variant. C/E is 8.6× lower, ECR_w is 4.4× higher, mean crossing angle is 10° larger. From a paper-headline perspective the choice is unambiguous: scenario 2 is the story you want to tell.

### The argument for keeping CPE

Scenario 1 has one subtle argument in its favour. In Step 3 of scenario 2, `bridge_edge_proportion` = 0.721. That means **almost three quarters of the visible edges are synthetic bridges**. A reviewer might ask "is that even a graph any more, or is it an abstraction?" Your soundness proof says yes, reachability is preserved, but visually this is no longer the same graph. Scenario 1 has `bridge_edge_proportion` = 0.373 (~37% bridges), so more of the "real" structure is preserved (CPE survives with `RUNS` and `HAS_VULN` edges).

In plain terms: scenario 2 reads like a summary ("attacker entry → root access on host"). Scenario 1 reads like a condensed chronicle ("attacker → host → vulnerable software → root access"). Each has its own audience.

### My recommendation

- **Headline body of the paper:** scenario 2 (Hide CPE+CWE+TI). The numbers are spectacular (C/E from 925.48 to 0.37 is a three-order-of-magnitude reduction), mean angle rises sharply, ECR_w = 24.93 is a citable headline number.
- **Appendix or discussion:** scenario 1 as the "preserve infrastructure context" alternative. Show that the mechanisms are composable and the analyst chooses the trade-off. A sysadmin keeps CPE because their reward is knowing "which software is vulnerable." A security analyst hides everything because their reward is knowing "where the attacker can go." The same set of mechanisms serves both roles.

This is also a strong illustration of one of your main paper points: *orthogonality of the mechanisms*. You demonstrate "minus one layer" and the reader sees exactly when it is worth applying.

---

## 3. Ten concrete change proposals

### 1. Change the default pipeline in section 6 of the metrics document — **RESOLVED**

You currently write *Step 3 - Hide internal types (hide CWE, hide TI - bridges materialise).* Change it to **hide CPE, CWE, TI** for the maximum-reduction variant, and keep *(alternative: hide CWE+TI to preserve infrastructure column)* as a parenthetical note. You have concrete data confirming the larger effect.

**Resolution.** `MetricsPaperReference.md § 6` recommends Hide CPE+CWE+TI as Step 3 with the alternative parenthetical. The rationale paragraph cites the C/E 925.48 → 0.37 swing.

### 2. ~~Investigate why `mean_chain_depth` = 1.6 in scenario 2~~ — RESOLVED, not a bug

The original suspicion was that hiding CPE+CWE+TI (three layers) should give an average chain depth of ~3. The actual distribution from Step 3 of scenario 2:

```
bridge_chain_length_distribution = { 1: 102, 2: 151 }
mean = (102·1 + 151·2) / 253 = 404/253 = 1.597 ✓
```

**This is correct behaviour, not a bug.** The reasoning in the original suspicion was wrong: chain_length accumulates only across **runs of consecutively-hidden types**, not the total count of hidden layers. PAGDrawer's schema `ATTACKER → HOST → CPE → CVE → CWE → TI → VC` has **CVE as a surviving anchor** between CPE and CWE+TI:

```
HOST → CPE → CVE → CWE → TI → VC
       └─┘   ✓    └─────┘
       hide  anchor  hide
       len=1         len=2
```

So the longest possible chain when hiding CPE+CWE+TI is **2** (the longer of the two runs split by the anchor). The distribution `{1: 102, 2: 151}` confirms this: 102 are HOST→CVE (CPE skipped), 151 are CVE→VC (CWE+TI skipped together). Zero of length 3 is **structurally impossible** without also hiding CVE.

**Paper-worthy insight.** This is actually an interesting M19 story unique to PAGDrawer's typed schema. Worth surfacing in the methodology section: "the chain-length distribution mirrors the position of the surviving anchor types in the schema; max chain ≤ longest hidden run." A reader looking at `bridge_chain_length_distribution` shouldn't expect a single peak — it'll be multimodal whenever multiple non-adjacent layers are hidden.

Updated (2026-05-05): MetricsPaperReference.md §2 (M19 spec) and DrawingQualityMetrics.md M19 sections document the anchor-type property.

### 3. Stress paradox after merge: add an alternative stress — **RESOLVED (option a)**

Caveat 4.3 says *stress_unreachable_pairs inflates after merge.* The data confirms this (scenario 2: 3967 → 7575 after merge, the wrong direction from what we want). Two options:

(a) Implement *visible-edge-only stress*: `stress_per_pair` computed only over pairs where BOTH nodes have at least one visible edge. This resolves the compound-children-disconnected case from 4.3.

(b) Or report `stress_per_visible_pair` next to the existing `stress_per_pair`. Two columns in the paper table and the reviewer sees for themselves which one is meaningful.

I would push for (a) because you only touch one line of code (a filter predicate) and you gain a metric that makes sense for every step of the pipeline.

**Resolution.** Option (a) implemented as `getStressEligibleNodes()` in `metrics.ts:229` — filters `getVisibleNodesWithIds()` further to nodes with at least one visible incident edge. Outcomes-merge children whose originals are now `display:none` get filtered out; prereqs-merge parents (no own edges) get filtered; ATTACKER_BOX (no edges) gets filtered. `stress_unreachable_pairs` no longer inflates structurally after merge. Documented in `MetricsPaperReference.md § 4.14` and `StressMetric.md`.

### 4. `top_pair_label` evolution: ready-made paper material — **EARMARKED**

Resolution: M25 evidence earmark added to `MetricsPaperReference.md § 6` (Recommended paper structure → item 4) listing the 5-step `top_pair_label` sequence and the JSON file paths. No code action; the breadcrumb is in the liaison doc so paper writing doesn't have to re-spelunk the example JSONs.

Your data shows the following evolution:

- Step 1: ENABLES × ENABLES (97.3%)
- Step 2: LEADS_TO × LEADS_TO (46.9%)
- Step 3: BRIDGE × BRIDGE (49.6%)
- Step 4: BRIDGE × ENABLES (41.9%)
- Step 5: BRIDGE × BRIDGE (70%)

This tells a perceptual story. Each mechanism "resolves" a different dominant pair. This is the M25 killer story and a **unique advantage of the heterogeneous schema** that no one else has. Give it a callout box or a small table in the paper.

### 5. Make ATTACKER_BOX explicit in the table caption — **EARMARKED**

In Step 3 you report `compound_groups_count` = 1, largest = 5. That is ATTACKER_BOX. After merge you have 10 compound_groups. A reviewer will not know what "1 compound" means before merge. State it in the table caption: *Step 1-3 compound count includes ATTACKER_BOX (5 attacker nodes); the merge step adds CVE_GROUP compound parents on top.*

Resolution: The exact caption sentence is already saved as Pitfall #4 in `MetricsPaperReference.md § 6` so it can be lifted verbatim into the paper table caption. No code change needed.

### 6. JSON schema: add `scan_timestamp` — **RESOLVED (five fields)**

`schema_version` = 1, `git_sha`, `app_version` are great. What is missing is *when Trivy ran the scan*. Trivy results change as NVD updates; without a scan timestamp, the same `image:tag` may report a different number of CVEs tomorrow. For replication, the moment of the scan matters (`trivy_scan_at: ISO-8601`). An alternative is to record a hash of the source Trivy JSON.

**Resolution.** Five Trivy-side reproducibility fields extracted at upload time and exposed in `data_source.scans_in_current_graph[*]`:

- `trivy_created_at` — Trivy's `CreatedAt` (actual scan time)
- `trivy_repo_digest` — `Metadata.RepoDigests[0]` (pinned image, byte-exact)
- `trivy_artifact_id` — `ArtifactID` (content hash)
- `trivy_report_id`   — `ReportID` (UUID per scan run)
- `trivy_version`     — Trivy scanner version

`uploaded_at` (PAGDrawer ingest time) kept alongside as a different dimension. Schema stays at v1 — these are additive optional fields. See `StatisticsModal.md` JSON example.

### 7. A stable variant of `bridges_share` — **DECLINED (acknowledged in caveat 4.13)**

Caveat 4.13 correctly warns that `bridge_edge_proportion` has *an unstable denominator* after merge. An alternative: `bridges_share` = bridges / (bridges + retained_originals), where retained_originals counts only non-`display:none` non-synthetic edges. More stable across steps. Or keep the current value but split it into components: `bridges_count`, `originals_visible_count`, `synthetics_count`. The reader can then compute any share they want.

**Decision.** Not implementing the stable variant. Caveat 4.13 was strengthened to "Critical for paper readers" with a denominator-breakdown table and the concrete nginx 0.27 → 0.93 swing, plus explicit guidance to prefer `bridge_edge_count` + `mean_contraction_depth` (absolute counts) over the proportion when comparing across the merge step. The proposed stable formulation is captured in the caveat as future-iteration work; for the GD 2026 deadline the absolute counts already give the right story without adding a new metric to maintain and document.

### 8. Validate `chain_length` against caveat 4.11.2 — **RESOLVED (test sentinels)**

The caveat warns that if someone runs *merge before hide*, chain_length is lost. In your recommended order (visibility before merge) this is not an issue. But add an **assertion to the test suite** that enforces this order (or an explicit warning in the UI when the user breaks the order). Otherwise, six months from now someone on the team will run *merge then hide* and the metrics will become unreliable.

**Resolution.** Two regression sentinels added to `frontend/js/features/metrics.test.ts`:

1. `chain_length invariants (caveat 4.11.2 sentinel)` — locks in the additive recurrence (`incoming + 1 + outgoing`) and the canonical mean range (≈ 1.0–2.5) for a known mixed distribution. Catches any future change that breaks the formula.
2. `cveMerge does not touch chain_length` — reads `cveMerge.ts` source at test time and asserts no `chain_length` / `chainLength` references appear in live code (comments stripped). Catches the moment a refactor starts mutating chain_length inside merge.

A runtime UI warning was considered but rejected: PAGDrawer's rebuild pipeline applies hide and merge atomically per rebuild — there is no user-visible "step 1 / step 2" ordering to check against. The trip-wire tests guard the *code-level* invariant that future refactors might break; a UI warning would have nothing to fire on under the current architecture.

See [`MetricsPaperReference.md` § 4.11](../_domains/MetricsPaperReference.md) for the updated caveat with sentinel cross-references.

### 9. Singleton fraction: drop from body, keep in JSON — **EARMARKED (no code change)**

In the current implementation `compound_singleton_fraction` will always be 0 (`cveMerge.ts:176` skips groups with size < 2). In the paper this is misleading: a reviewer reads "100% of groups have >1 element... how could it be otherwise?" Keep the metric as a **regression sentinel in unit tests**, but do not report it in the paper table. Otherwise it is visual noise.

Resolution: leave the metric in JSON and the Statistics modal as-is (it stays useful as a regression sentinel and a debugging signal). The decision *not to put it in the paper body* is captured as Pitfall #6 in `MetricsPaperReference.md § 6`. Same place explains the ATTACKER_BOX-as-the-only-compound-before-merge note (Pitfall #4), so the paper-writer sees both at once.

### 10. SVG vs JSON: are SVGs for figures? — **DEFERRED (PDF-era)**

You have five SVGs and five JSONs per scenario. The question: are the SVGs raw Cytoscape layout snapshots, or are they rendered for the paper? If the latter, add a script that normalises the style (font, grayscale-friendly path colours, no colour-only labels for black-and-white printing). For submission, everything must be readable in a black-and-white printout. I would write a small Python or Inkscape script to do the pretty-print conversion.

Resolution: deferred. GD 2026 papers are read on PDFs in colour; grayscale-printability is no longer the default expectation. Pick this up only if a reviewer asks for it.

---

## 4. Five reflection questions

**Q1.** Should ATTACKER_BOX be excluded from `compound_groups_count` before merge? Currently you report `compound_groups` = 1 in Step 1, where the "1" is ATTACKER_BOX. This is misleading for a reader who does not know ATTACKER_BOX exists. Maybe report two numbers: `compound_groups_count_excl_attacker` and `compound_groups_total`?

**Q2.** Should Step 3 (hide layers) be shown in the paper for *both* variants (with and without CPE) as a side-by-side comparison? That would give the reviewer an immediate answer to "what if we keep CPE?" instead of just one number.

**Q3.** The asymmetry of bridge depth (1.6 vs 2.0) could be a strong argument. It shows that the *real* graph is not as regular as the schema suggests. Worth reporting not only the mean depth but also the **standard deviation of chain length**, so the reviewer sees whether bridges are uniform or varied?

**Q4.** Stress normalisations (four σ variants) - which to report in the body? I would recommend `stress_per_pair_normalized_edge` (Kamada-Kawai) because it is the most-cited convention. The other three go into the appendix. The data backs this up: values are in the 1-15 range (human-interpretable), unlike raw `stress_per_pair` whose values reach 10⁹.

**Q5.** LEADS_TO × LEADS_TO as the top pair in Step 2 (after the granularity slider). This means the TI nodes after VC:HOST have many outgoing edges to different VC-host pairs. Is this *intentional* or an artefact? If TI:CWE granularity (your current setting) is creating fan-out, then a TI granularity slider could reduce further before the hide step. Worth dropping TI:HOST in as a Step 2.5?

---

## 5. Validating the document's predictions

Section 3 of `MetricsPaperReference.md` predicts how each metric should move under each mechanism. I checked the predictions against the nginx data:

| Mechanism | Prediction | Observation |
|---|---|---|
| Granularity slider | N, E, C/E decrease | yes: 830 → 543, 5675 → 920, 925 → 13 |
| Hide CWE+TI | bridges 0 → >0, depth = 2 | yes: bridges = 151, depth = 2.0 |
| Hide CPE+CWE+TI | depth = 3 expected | flag: observed 1.6 |
| Merge by outcomes | ECR 0 → >1 | yes: 0 → 4.54 (sc.1), 0 → 19.06 (sc.2) |
| Merge by outcomes | stress_unreachable rises | yes: 10187 → 15146 (sc.1) |
| Exploit paths | N, E decrease | yes: 179 → 103 (sc.1), 125 → 78 (sc.2) |

Most predictions hold cleanly. The single position that needs investigation: mean bridge contraction depth in scenario 2 (expected ~3, observed 1.6). See change proposal 2 above.

---

*Document prepared as a punch list for changes to land before the GD 2026 deadline (13 May 2026, abstract 6 May). All numbers come from JSON exports captured on 5 May 2026 from PAGDrawer version 1.0.0, commit 00f46fc.*
