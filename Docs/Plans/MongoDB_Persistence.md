# MongoDB Persistence for NVD / EPSS / CWE Data — Implementation Plan

**Branch:** `feature/mongodb-persistence`
**Created:** 2026-04-20

## Goal

Replace the current file-based caches (`src/data/cache/*.json`) with a MongoDB-backed
persistence layer. Add a progress bar during enrichment and a force-refresh
option to bypass TTL.

No migration — first rebuild after switching populates Mongo from live sources.

---

## Decisions Locked In

| # | Decision |
|---|----------|
| 1 | All three caches (NVD, EPSS, CWE) move to MongoDB |
| 2 | Fail fast if Mongo is unavailable (no file-cache fallback) |
| 3 | Polling-based progress bar (FastAPI GET endpoint, 500 ms client interval) |
| 4 | Force-refresh: both a global "Refresh all NVD data" button AND a per-rebuild checkbox |
| 5 | docker-compose.yml at repo root, no auth for local dev |
| 6 | Sync pymongo + asyncio.to_thread in FastAPI handlers |
| 7 | Single concurrent rebuild job; return 409 if another is active |
| 8 | No migration — first rebuild re-fetches everything |
| 9 | Named Docker volume `mongodb_data` |

---

## Architecture

### Current flow
```
Trivy JSON → /api/data/rebuild → TrivyDataLoader
  └─ enrich_from_nvd=True → NVDFetcher (reads/writes nvd_cache.json, epss_cache.json)
  └─ enrich_cwe=True       → CWEFetcher (reads/writes cwe_cache.json)
→ KnowledgeGraphBuilder → Graph
```

### New flow
```
Trivy JSON → /api/data/rebuild → starts rebuild job, returns job_id
  └─ background task:
       TrivyDataLoader
         └─ enrich_from_nvd=True → NVDFetcher (reads/writes MongoDB)
         └─ enrich_cwe=True       → CWEFetcher (reads/writes MongoDB)
         └─ reports progress every N CVEs to MongoDB job document
       KnowledgeGraphBuilder

Client: polls /api/data/rebuild/progress/<job_id> every 500 ms
        updates progress bar in sidebar/modal
```

---

## MongoDB Schema

Database: `pagdrawer`

### Collection: `nvd_cves`
```
{
  _id: "CVE-2021-44228",
  description: "...",
  cvss_vector: "CVSS:3.1/AV:N/AC:L/...",
  cvss_score: 10.0,
  severity: "CRITICAL",
  cwe_ids: ["CWE-502"],
  published: "...",
  modified: "...",
  references: [...],
  cached_at: ISODate("2026-04-20T14:00:00Z"),
  source: "nvd"
}
```
TTL: 7 days (soft — checked in code when reading, not MongoDB TTL index).
**Rationale**: a MongoDB TTL index *deletes* documents; we want stale records
still present so "force refresh" can compare or reuse fields not being updated.

Index: `cached_at` (ascending) for admin queries.

### Collection: `epss_scores`
```
{
  _id: "CVE-2021-44228",
  epss_score: 0.97,
  percentile: 99.3,
  cached_at: ISODate(...)
}
```
TTL: 7 days (soft).

### Collection: `cwe_impacts`
```
{
  _id: "CWE-502",
  technical_impacts: ["Execute Unauthorized Code or Commands", ...],
  name: "...",
  description: "...",
  cached_at: ISODate(...),
  source: "static" | "rest" | "fallback"
}
```
TTL: 30 days (CWEs change rarely).

### Collection: `rebuild_jobs`
```
{
  _id: "job-uuid",
  status: "running" | "completed" | "failed",
  started_at: ISODate(...),
  completed_at: ISODate(...) | null,
  total_cves: 234,
  processed_cves: 87,
  current_cve: "CVE-2023-xxxxx",
  current_phase: "nvd" | "cwe" | "building_graph",
  error: null | "...",
  stats: null | { ... }   // final graph stats on completion
}
```
Only one document with `status: running` at any time.
TTL index on this collection: 1 hour (cleanup completed/failed jobs automatically).

---

## Files to Change / Add

### New files
| File | Purpose |
|------|---------|
| `docker-compose.yml` | Mongo service + app service + volume |
| `Dockerfile` | (optional — only if running app in container too) |
| `src/data/mongo_client.py` | Singleton Mongo connection, TTL check helpers |
| `src/data/jobs.py` | `JobManager` for rebuild-job lifecycle (create, update progress, complete) |
| `Scripts/start-mongo.sh` | Start only the Mongo container |
| `Scripts/kill-mongo.sh` | Stop and remove the Mongo container |
| `tests/test_mongo_persistence.py` | Uses `mongomock` or testcontainers — TBD |
| `frontend/js/features/rebuildProgress.ts` | Polling + progress bar UI |
| `frontend/js/services/api.ts` | Add `fetchRebuildProgress(jobId)` |

### Modified files
| File | Change |
|------|--------|
| `src/data/loaders/nvd_fetcher.py` | Replace JSON load/save with Mongo read/upsert; accept optional `job_id` for progress reporting |
| `src/data/loaders/cwe_fetcher.py` | Same |
| `src/data/loaders/trivy_loader.py` | Pass `job_id` through to fetchers; report per-CVE progress |
| `src/viz/app.py` | `/api/data/rebuild` becomes async background job; add `/api/data/rebuild/progress/<job_id>`; add `/api/data/force_refresh` (global) |
| `requirements.txt` | Add `pymongo`, optionally `mongomock` for tests |
| `.env.example` | `MONGODB_URI=mongodb://localhost:27017` |
| `.gitignore` | Keep `src/data/cache/` ignored; add `mongodb_data/` if volume isn't Docker-managed |
| `frontend/index.html` | Progress-bar element (modal or sidebar) |
| `frontend/css/styles.css` | Progress-bar styles |
| `frontend/js/features/dataSource.ts` | Replace "Rebuild" click handler to launch job + poll; wire the Force Refresh checkbox |
| `CLAUDE.md` | Mention Mongo as a dependency |

---

## Task Breakdown

### Phase 1: Infrastructure
1. **Add pymongo to requirements.txt** and install.
2. **Create `docker-compose.yml`** with Mongo 7 service on port 27017, named volume `mongodb_data`.
3. **Create `Scripts/start-mongo.sh` and `kill-mongo.sh`**.
4. **Create `src/data/mongo_client.py`**: singleton client, DB accessor, TTL-aware get/set helpers.
5. **Fail-fast check** on app startup: attempt Mongo ping, raise if unreachable.

### Phase 2: Fetcher refactor (non-breaking)
6. **Refactor `nvd_fetcher.py`**: replace `_load_cache()` / `_save_cache()` with Mongo operations. Keep method signatures; callers don't change.
7. **Refactor `cwe_fetcher.py`**: same.
8. **Add TTL check**: when reading, compute `datetime.utcnow() - cached_at`; if > TTL, fetch fresh (unless `force_refresh=True`).
9. **Add `force_refresh` parameter** to fetcher constructors/methods (default False).

### Phase 3: Job system
10. **Create `src/data/jobs.py`**: `JobManager` class with `create_job()`, `update_progress(job_id, processed, current_cve, phase)`, `complete_job(job_id, stats)`, `fail_job(job_id, error)`.
11. **Modify `trivy_loader.py`** to accept an optional `job_manager` and report per-CVE.
12. **Modify `/api/data/rebuild`**: kick off a `BackgroundTask` returning `{job_id: "..."}` immediately. Check for existing running job → 409.
13. **Add `/api/data/rebuild/progress/<job_id>`**: returns the job document as JSON.
14. **Add `/api/data/force_refresh`**: clears cached_at on all NVD/EPSS docs (makes them stale on next fetch). Returns 200.

### Phase 4: Frontend
15. **Add progress bar HTML** (progress bar + current-CVE label + spinner) in a dedicated div.
16. **Create `rebuildProgress.ts`**: `startRebuild()` calls the API, gets job_id, starts polling, updates DOM every 500 ms until `status != running`.
17. **Modify `dataSource.ts`**: rebuild button calls `startRebuild()` instead of the old synchronous flow. Disable button during rebuild.
18. **Add Force Refresh checkbox** to rebuild dialog.
19. **Add "Refresh all NVD data" button** to Settings modal under a new "Data Management" section.

### Phase 5: Tests
20. **Unit tests** for `mongo_client.py` (TTL logic) using `mongomock`.
21. **Unit tests** for `JobManager`.
22. **Integration tests** for fetchers against `mongomock`.
23. **Frontend tests** for the progress-polling state machine (mock fetch, simulate server responses).

### Phase 6: Documentation
24. **Update `CLAUDE.md`**: "Requires MongoDB — use `bash Scripts/start-mongo.sh`".
25. **Update `Docs/_projectStatus/`** with a new snapshot.
26. **Create daily note** in `Docs/_dailyNotes/`.
27. **Add a domain doc** `Docs/_domains/MongoDBPersistence.md` if the system is non-trivial.

---

## Risks and Open Questions

### Risks
- **Background task cancellation**: if the user cancels the Trivy upload mid-flight, the background task keeps running. Mitigation: add `/api/data/rebuild/cancel/<job_id>` that flips a flag the fetcher checks.
- **Concurrent Mongo writes from multiple clients**: low risk for local-dev tool, ignored.
- **First rebuild is slow**: at 6 s NVD rate limit × 200 CVEs ≈ 20 min. The progress bar makes this tolerable, but user should be warned on first load. Mitigation: add a one-time "This may take 20 minutes on first run" notice.
- **Mongo connection pool exhaustion**: pymongo default pool is 100; we'll stay well under.

### Open questions to address during implementation
- **Which python driver**: stick with `pymongo` sync (decided); re-evaluate only if perf becomes an issue.
- **Schema evolution**: use a `schema_version` field on each document? Not in MVP, add later if schema changes.
- **Should the `app` service run in Docker too** (full docker-compose) or does the user run the backend locally and only Mongo in Docker? **Lean: Mongo-only in Docker** (simpler, no rebuild of the Python image on code changes). User keeps `Scripts/start-backend.sh`.

---

## Acceptance Criteria

- [ ] `bash Scripts/start-mongo.sh` brings up Mongo; `Scripts/kill-mongo.sh` stops it cleanly
- [ ] Backend fails fast with a clear error if Mongo is unreachable
- [ ] First rebuild after a fresh Mongo container populates NVD/EPSS/CWE collections
- [ ] Second rebuild with same data uses cached data (observable: rebuild finishes in seconds)
- [ ] TTL expiry triggers re-fetch after 7 days (testable by manually setting `cached_at` older)
- [ ] Progress bar shows during rebuild, with phase + current CVE + N/total
- [ ] "Force refresh" checkbox on rebuild bypasses TTL
- [ ] "Refresh all NVD data" button invalidates all cached_at timestamps
- [ ] Concurrent rebuilds return 409 Conflict
- [ ] All existing tests still pass
- [ ] New tests cover mongo client, job manager, fetcher persistence

---

## Implementation Order

Roughly the phases above, but I'd recommend splitting into sub-PRs if the feature branch grows too large:

1. **Sub-PR A**: Infrastructure (docker-compose, mongo_client, requirements). Zero user-facing change — just adds Mongo as a dependency. Fetchers still use file cache.
2. **Sub-PR B**: Migrate fetchers to Mongo. Remove file cache. Tests updated. Breaking change.
3. **Sub-PR C**: Job system + progress bar (background task, polling endpoint, frontend UI).
4. **Sub-PR D**: Force-refresh controls + Settings panel.

Alternatively, one large branch merged all at once. User preference?
