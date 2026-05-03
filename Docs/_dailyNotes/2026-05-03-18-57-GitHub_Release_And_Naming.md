# 2026-05-03 - First Public Release on GitHub + Project-Name Correction

## Overview

Two related milestones: PAGDrawer is now public on GitHub at https://github.com/tmachalewski/PAGDrawer under Apache 2.0, and the project name was corrected to its real expansion — **Probabilistic Attack Graph Drawer** (previously written as "Privilege-based" / "Predictive" / "Knowledge Graph Visualization" in different places).

---

## 1. GitHub publication

### Decisions

| Question | Choice | Rationale |
|----------|--------|-----------|
| Default branch name | `main` | GitHub default; `master` renamed locally before push (`git branch -m master main`) |
| Initialize repo with README/LICENSE/.gitignore on GitHub? | No | Would create a divergent commit on the remote with no common ancestor; cleanest path is to push the existing local history into an empty repo |
| License | Apache 2.0 | Permissive (anyone can use/fork/modify) plus explicit patent grant; appropriate for a research-led tool |
| Push only main, or all branches? | All 13 | All feature branches were already merged; pushing them preserves the per-feature commit history for review |
| Backend in Docker? | No (still local via `Scripts/`) | Decided earlier; only Mongo runs in Docker |

### Commands actually run

```bash
git branch -m master main
git remote add origin https://github.com/tmachalewski/PAGDrawer.git
git push -u origin main
git push origin --all   # 13 feature branches
```

13 feature branches now live on the remote alongside `main`:

- `feature/chain-depth-aware-attacks`
- `feature/cve-merge-modes`
- `feature/graph-quality-metrics`
- `feature/grouping-slider`
- `feature/merge-legend-filters`
- `feature/mongodb-persistence` (integration branch)
- `feature/mongodb-persistence-A-infra`
- `feature/mongodb-persistence-B-fetchers`
- `feature/mongodb-persistence-C-progress`
- `feature/scan-selection`
- `feature/trivy-upload-ui`
- `fix/e2e-test-timing`
- `claude/admiring-ramanujan`

---

## 2. README

Top-of-page screenshot of the actual UI (Node.js Alpine scan, CVEs merged + Exploit Paths active), then a before/after pair of pure SVG exports (full alpine_edge graph → progressively simplified version).

Sections: project tagline · screenshots · features list · quick-start commands (`Scripts/start-mongo.sh`, `Scripts/start-backend.sh`, `Scripts/start-frontend.sh`) · test commands · tech stack table · pointers into `Docs/_projectStatus/`, `Docs/_domains/`, `Docs/_dailyNotes/`, `Docs/Plans/` · research-foundation citations.

Filenames in markdown links use URL-encoding for the spaces and parentheses Windows kept in the SVG / image filenames.

---

## 3. License

Full Apache 2.0 text in `LICENSE` at the repo root. Copyright line updated to `Copyright 2026 Tomek Machalewski`. GitHub auto-detects the license and shows it in the repo sidebar.

---

## 4. Project-name correction

**The expansion is "Probabilistic Attack Graph Drawer".**

Wrong expansions found and replaced:

| Location | Was | Now |
|----------|-----|-----|
| `README.md` | "Privilege-based Attack Graph Drawer" | "Probabilistic Attack Graph Drawer" |
| `frontend/index.html` `<title>` | "PAGDrawer - Knowledge Graph Visualization" | "PAGDrawer - Probabilistic Attack Graph Drawer" |
| `frontend/index.html` logo subtitle | "Predictive Attack Graph Drawer" | "Probabilistic Attack Graph Drawer" |
| `Docs/_projectStatus/2026-04-20-15-55-Project_State_Overview.md` | "Privilege-based..." | "Probabilistic..." |

Older project-status snapshots (`X_*` and 2026-01 / 2026-04-10 / 2026-04-11 files) intentionally left as-is — they're historical records of how the project was described at the time, not living documentation.

The repository directory and all code identifiers stay `PAGDrawer` / `pagdrawer` regardless.

---

## 5. Files added / modified

**New**:
- `README.md`
- `LICENSE` (Apache 2.0)
- `examples/_UI/UI 2026-04-21 183058.jpg` (screenshot for README)

**Modified**:
- `frontend/index.html` (title + subtitle)
- `Docs/_projectStatus/2026-04-20-15-55-Project_State_Overview.md` (name fix)

---

## 6. Commits

```
ee25346 docs: Add UI screenshot to README
c28e0bc docs: Fix PAGDrawer expansion — "Probabilistic Attack Graph Drawer"
153d516 docs: Swap README screenshots to alpine_edge before/after pair
4fc8411 docs: Add README with screenshots and Apache 2.0 LICENSE
```
