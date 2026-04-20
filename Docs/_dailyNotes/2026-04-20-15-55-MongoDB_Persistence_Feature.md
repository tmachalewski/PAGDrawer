# 2026-04-20 - MongoDB Persistence for NVD/EPSS/CWE + Background Rebuild Jobs

## Overview

Biggest architectural change since the TypeScript migration. Replaced three JSON-file caches (`nvd_cache.json`, `epss_cache.json`, `cwe_cache.json`) with a MongoDB-backed persistence layer, and introduced a background rebuild job system with a progress bar so long rebuilds (NVD rate-limits at 6s/CVE → 20 min for a 200-CVE scan) don't block the HTTP request or leave the user staring at a spinner.

Shipped in three sub-PRs (Phase A, B, C) each merged individually into an integration branch, then merged to master as a single feature.

---

## 1. Motivation

| Problem with JSON files | Why Mongo |
|-------------------------|-----------|
| Opaque blob on disk, hard to inspect | Query via Compass / PyCharm / mongosh |
| Atomic write races when multiple processes ran | Single source of truth with native atomic upsert |
| Occasional drift from online sources never surfaced | Explicit TTL check; force-refresh option |
| Loading the whole file into memory on startup | Lazy per-key queries |

And for the rebuild endpoint:

| Problem | Fix |
|---------|-----|
| 20-minute synchronous request → browser timeout risk | Background thread + job_id + polling |
| No visibility into what's happening | Progress bar with phase + N/total + current CVE |
| Can't abort a runaway rebuild | Cancel endpoint + flag checked between CVEs |
| Concurrent rebuilds would scramble state | 409 Conflict on second attempt |

---

## 2. MongoDB Schema

Database: `pagdrawer`

### `nvd_cves`
```
{
  _id: "CVE-2021-44228",
  description: "...", cvss_vector: "...", cvss_score: 10.0,
  severity: "CRITICAL", cwe_ids: [...],
  published: "...", modified: "...", references: [...],
  epss_score: 0.97,
  cached_at: ISODate(...),
  source: "nvd"
}
```

### `epss_scores`
```
{ _id: "CVE-2021-44228", epss_score: 0.97, cached_at: ISODate(...) }
```

### `cwe_impacts` (unified impacts + info)
```
{
  _id: "CWE-502",
  technical_impacts: ["Execute Unauthorized Code or Commands", ...],
  name: "...", description: "...",
  source: "static" | "rest",
  cached_at: ISODate(...)
}
```

### `rebuild_jobs`
```
{
  _id: "<uuid>",
  status: "running" | "completed" | "failed" | "cancelled",
  phase: "loading" | "enriching_nvd" | "enriching_cwe" | "building_graph" | "done",
  started_at: ISODate(...), completed_at: ISODate(...),
  total_cves: 234, processed_cves: 87,
  current_cve: "CVE-2024-xxxxx",
  cancel_requested: false,
  error: null | "...",
  stats: null | {...}
}
```

### TTL strategy — **soft TTL, not index-based**

We check `datetime.utcnow() - cached_at > TTL` in Python on each read. Why not a MongoDB TTL index that auto-deletes?

- **Soft TTL**: stale records stay queryable. Admin tools can diff old vs new after a force-refresh. Useful for debugging drift.
- **Force-refresh is a backdate**: `invalidate_collection()` sets `cached_at` to epoch, making everything instantly stale without losing any data.
- **No auto-delete surprises** — stale records re-populate on next use, not on a background cleaner's schedule.

Defaults: NVD 7d, EPSS 7d, CWE 30d (CWE changes rarely).

---

## 3. Phase A — Infrastructure

**Shipped**: docker-compose, scripts, Mongo client singleton.

Key decisions:

- **Docker only for Mongo** — backend/frontend still run locally via existing Scripts/. Keeps dev iteration fast (no image rebuilds on code change).
- **No auth for local dev** — `MONGODB_URI=mongodb://localhost:27017` default, override via env var.
- **Fail-fast on startup** — `init_mongo()` pings Mongo with 3s timeout; raises `RuntimeError` with clear remediation ("Start it with bash Scripts/start-mongo.sh") if unreachable.
- **`PAGDRAWER_SKIP_MONGO=1` env var** — lets pytest runs skip the startup ping for isolated tests.

Singleton pattern in `mongo_client.py`:

```python
_client: Optional[MongoClient] = None
_db: Optional[Database] = None

def init_mongo(...): -> pings, stores in _client / _db
def get_db() -> raises if not initialized
def close_mongo() -> for tests
```

TTL helpers:

```python
cached_doc_if_fresh(collection, doc_id, ttl_days, force_refresh) -> Optional[doc]
upsert_cached_doc(collection, doc_id, payload)   # auto-sets cached_at
invalidate_collection(collection) -> int          # backdate for refresh
is_fresh(cached_at, ttl_days) -> bool
```

16 unit tests covering all helpers (`test_mongo_client.py`) using `mongomock`.

---

## 4. Phase B — Fetcher Migration

**Shipped**: `NVDFetcher` and `CWEFetcher` rewritten to read/write Mongo instead of JSON files.

### Approach

- Constructor signatures changed:
  - Old: `NVDFetcher(nvd_cache_file=..., epss_cache_file=...)`
  - New: `NVDFetcher(nvd_api_key=None, force_refresh=False)`
  - Old: `CWEFetcher(cache_file=...)`
  - New: `CWEFetcher(timeout=30, force_refresh=False)`

- In-memory `_nvd_cache` / `_epss_cache` / `_cache` / `_info_cache` dicts removed. Every lookup goes to Mongo.
- `_load_caches()` / `_save_*_cache()` methods deleted.
- `_is_cache_valid()` replaced by `mongo_client.is_fresh()`.
- `clear_cache()` now does `collection.delete_many({})`.
- `get_cache_stats()` now queries `count_documents({})`.

### Unified CWE document

Previously the JSON had `{impacts: {}, info: {}}` at the top level — two parallel dicts. In Mongo these merged into one document per CWE with fields `technical_impacts`, `name`, `description`, `source` — less structure-wrangling, simpler queries.

### Static CWE mapping deactivated

`STATIC_CWE_MAPPING` is an in-code Python dict of ~166 common CWEs (hand-curated by a previous contributor). With file caches, it made sense to short-circuit there to avoid network calls. With Mongo, the short-circuit meant the `cwe_impacts` collection stayed empty whenever every scanned CWE was already in the dict — confusing for users inspecting the database.

Initially added a Mongo upsert on first static encounter (so the collection populates either way). User then asked to disable the static path entirely to validate that live REST data matches or improves on the in-code constant. Gated it behind:

```python
class CWEFetcher:
    USE_STATIC_MAPPING: bool = False   # TODO: re-enable after validation
```

Tests cover both modes (flag on / off). 48 total in `test_cwe_fetcher.py`.

### Test migration

`tests/conftest.py` gained a shared `mock_mongo` fixture that installs a `mongomock.MongoClient` as the singleton for one test, then tears it down. Used by `test_mongo_client.py`, `test_nvd_fetcher.py`, `test_cwe_fetcher.py`, `test_jobs.py`, and — via the `client` fixture — `test_api_endpoints.py`.

Cache-file-specific tests deleted (redundant with `test_mongo_client.py`). Enrichment / parsing tests kept, just stripped the file-path fixture params.

---

## 5. Phase C — Background Jobs + Progress Bar

**Shipped**: `JobManager`, background-thread worker, polling endpoint, progress bar UI, cancel.

### Why threading.Thread, not asyncio

Two options considered:

1. **aiohttp + motor async** — elegant, but the bottleneck is NVD's 6-second rate limit per request, not I/O concurrency. Migrating the fetchers to async would be a large refactor for negligible perf gain.
2. **Keep pymongo sync, run worker on a thread** — minimal churn. FastAPI's `BackgroundTasks` runs after the response completes. Spawning a `threading.Thread` from there lets the worker block on urllib calls without stalling the event loop.

Chose option 2. The event loop stays responsive for polling because the worker thread is out of its way.

### Job lifecycle

```
create_job()   → status=running, job_id=uuid
update_progress(processed_cves, current_cve, phase, total_cves)
complete_job(stats)   → status=completed
fail_job(error)       → status=failed
request_cancel()      → sets cancel_requested=true (returns True if running)
cancel_finalize()     → status=cancelled (called by worker after noticing)
purge_old_jobs(sec)   → deletes completed/failed/cancelled older than N sec
```

Concurrency protection: `create_job()` returns `JobExistsError` if any doc has `status=running`. The API surfaces this as `409 Conflict`.

### Progress points in the loader

`TrivyDataLoader` learned three new optional params: `job_manager`, `job_id`, `force_refresh`. In `load()`:

```
_report_phase(PHASE_LOADING)
... parse JSON, count unique CVEs ...
_report_total(unique_cve_count)
_report_phase(PHASE_NVD)

for each CVE:
    if _check_cancel(): raise CancelledError
    _report_progress(processed, current_cve)    # shown in UI before enrichment
    _create_cve(...)
    processed += 1
    _report_progress(processed, current_cve)    # after enrichment
```

Progress is reported **before** the NVD call so the UI sees `current_cve` change the moment a slow fetch starts, not just at the end.

### Cancel semantics

Checked at the top of each CVE iteration. In the worst case, a pending `fetch_cve` that's waiting on the NVD rate-limiter will finish (~6s) before the loader notices the cancel. Good enough for "oh wait, wrong scan" — not good enough for instant abort. Documented this as a known limitation.

### API endpoints

```
POST   /api/data/rebuild               → { status: "started", job_id }  (or 409)
GET    /api/data/rebuild/progress/{id} → full job document (JSON)
POST   /api/data/rebuild/cancel/{id}   → { status: "cancel_requested" }
```

Query params preserved: `enrich`, `use_deployment`, `scan_ids[]`, and new `force_refresh`.

### Frontend polling

`frontend/js/features/rebuildProgress.ts`:

```typescript
rebuildWithProgress(enrich, scanIds, forceRefresh, callbacks)
  → startRebuild() → job_id
  → loop: fetchRebuildProgress(job_id) every 500ms
         render phase + N/total + current CVE + fill %
         cancel button calls cancelRebuild(job_id)
  → terminal state → return / throw
```

Progress bar sits in the data source panel. Hidden by default, shown during rebuild, hidden on completion/cancel.

Legacy `rebuildData()` kept as a synchronous polling wrapper for any code that expected it to block. Shouldn't be needed after this change, but easier than auditing all call sites.

### CSS

Linear-gradient fill (indigo → green), tabular-numerics for the count line, monospace for the current CVE ID. Light-theme variants included.

---

## 6. Files Changed

**New**:
- `docker-compose.yml`
- `.env.example`
- `Scripts/start-mongo.sh`, `Scripts/kill-mongo.sh`
- `src/data/mongo_client.py`
- `src/data/jobs.py`
- `tests/test_mongo_client.py` (16 tests)
- `tests/test_jobs.py` (17 tests)
- `frontend/js/features/rebuildProgress.ts`
- `Docs/Plans/MongoDB_Persistence.md`

**Modified**:
- `src/data/loaders/nvd_fetcher.py`, `src/data/loaders/cwe_fetcher.py`
- `src/data/loaders/trivy_loader.py` (progress hooks, cancel check)
- `src/viz/app.py` (rebuild endpoint + 2 new endpoints)
- `tests/conftest.py` (mock_mongo fixture)
- `tests/test_nvd_fetcher.py`, `tests/test_cwe_fetcher.py` (rewrote cache tests for Mongo)
- `tests/test_api_endpoints.py` (async rebuild flow)
- `frontend/js/services/api.ts` (startRebuild, fetchRebuildProgress, cancelRebuild)
- `frontend/js/features/dataSource.ts` (new rebuildWithProgress flow)
- `frontend/index.html` (progress bar + force-refresh checkbox)
- `frontend/css/styles.css` (progress bar styles)
- `CLAUDE.md` (Mongo dependency note)
- `requirements.txt` (pymongo, mongomock)

---

## 7. Test Count

- **Backend**: 344 → 381 tests (+16 mongo_client, +17 jobs, +4 API endpoint)
- **Frontend**: 153 → 156 tests (+3 API service tests)
- **Total**: ~497 → **537**

Legacy tests that hit the cache-file path (init-creates-empty, init-loads-existing, cache-validation) were deleted — their coverage lives in `test_mongo_client.py` now.

---

## 8. Known Limitations

| Issue | Mitigation |
|-------|-----------|
| First rebuild is slow (6s × N CVEs) | Progress bar makes it tolerable; subsequent runs are fast (Mongo hit) |
| Cancel lag up to 6s | Documented; flag is checked between CVEs, not inside an NVD call |
| No offline mode | Mongo is now mandatory — start it via `Scripts/start-mongo.sh` |
| Single-user — no per-user job isolation | By design for local dev tool; 409 on concurrent |

---

## 9. Deferred Work

- **Phase D** — global "Refresh all NVD data" button in the Settings modal (would call `invalidate_collection` for nvd_cves + epss_scores). Per-rebuild force-refresh checkbox already works.
- **Re-enable `USE_STATIC_MAPPING`** — after validating that live REST-sourced CWE impacts match or improve on the in-code constant.

---

## 10. Git Flow

```
master
└── feature/mongodb-persistence                      (integration branch)
      ├── feature/mongodb-persistence-A-infra        → merged
      ├── feature/mongodb-persistence-B-fetchers     → merged
      └── feature/mongodb-persistence-C-progress     → merged
```

Each sub-PR was committed and reviewed independently; the integration branch merged to master as one cohesive feature (commit `884e778`).
