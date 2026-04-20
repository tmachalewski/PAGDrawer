# MongoDB Persistence

This document describes how PAGDrawer uses MongoDB to persist external-API data (NVD CVE records, EPSS exploit-probability scores, and CWE technical-impact mappings) and to track long-running rebuild jobs. It supersedes the file-based JSON caches that lived in `src/data/cache/` before v2.0.

For the step-by-step *how we built it* history, see `Docs/Plans/MongoDB_Persistence.md` and the daily note at `Docs/_dailyNotes/2026-04-20-15-55-MongoDB_Persistence_Feature.md`.

---

## Why MongoDB?

- **Observable** — any SQL/NoSQL GUI (PyCharm, Compass, Studio 3T) can inspect the cache state during development
- **Atomic upsert semantics** — no read-modify-write races between concurrent fetches
- **Persistent across restarts** via a named Docker volume
- **Soft TTL** — we keep stale records queryable rather than auto-deleting them, so "force refresh" can backdate without losing data
- **Natural fit for heterogeneous cache payloads** (each document already has its own schema — no migration overhead for small field additions)

Sync `pymongo` is used rather than async `motor`. The bottleneck is NVD's 6 s/request rate limit, not I/O concurrency, so the simpler driver is justified.

---

## Architecture at a Glance

```
┌────────────────────┐      ┌───────────────────────────┐
│  FastAPI handler   │      │  Background worker thread │
│                    │      │  _run_rebuild_job()       │
│  POST /rebuild     │────►│                            │
│  returns job_id    │      │  TrivyDataLoader          │
└─────────┬──────────┘      │      │                    │
          │                 │      ▼                    │
          │                 │  NVDFetcher / CWEFetcher  │
          │                 │      │                    │
          ▼                 │      ▼                    │
  ┌────────────────┐        │  ┌──────────────────┐    │
  │ /progress/{id} │──◄──── │──│  mongo_client    │    │
  │ /cancel/{id}   │        │  │  (singleton)     │    │
  └────────────────┘        │  └────────┬─────────┘    │
                            └───────────┼──────────────┘
                                        ▼
                                 ┌──────────────┐
                                 │   MongoDB 7  │
                                 │              │
                                 │ nvd_cves     │
                                 │ epss_scores  │
                                 │ cwe_impacts  │
                                 │ rebuild_jobs │
                                 └──────────────┘
```

---

## Collections

All in the `pagdrawer` database (override via `MONGODB_DB` env var).

### `nvd_cves`

Cached CVE records from the NIST NVD REST API.

| Field          | Type       | Notes                                                |
| -------------- | ---------- | ---------------------------------------------------- |
| `_id`          | string     | CVE ID, e.g. `CVE-2021-44228`                        |
| `id`           | string     | Same as `_id` (kept for legacy consumers)            |
| `description`  | string     | English description                                  |
| `cvss_vector`  | string     | CVSS v3.1 vector                                     |
| `cvss_score`   | number     | Base score                                           |
| `severity`     | string     | CRITICAL / HIGH / MEDIUM / LOW                       |
| `cwe_ids`      | [string]   | Associated CWE IDs                                   |
| `published`    | string     | Publication timestamp (ISO)                          |
| `modified`     | string     | Last modified timestamp (ISO)                        |
| `references`   | [object]   | Up to 5 reference URLs                               |
| `epss_score`   | number     | Cached EPSS (optional; fetched separately)           |
| `cached_at`    | ISODate    | UTC timestamp of last write — drives TTL             |
| `source`       | string     | `"nvd"`                                              |

TTL: **7 days** (soft; checked in Python, see `mongo_client.TTL_NVD_DAYS`).

### `epss_scores`

EPSS (Exploit Prediction Scoring System) scores from FIRST, kept separate because they're fetched via a different API (batch-capable) with different rate limits.

| Field          | Type    | Notes                                     |
| -------------- | ------- | ----------------------------------------- |
| `_id`          | string  | CVE ID                                    |
| `epss_score`   | number  | Probability of exploitation within 30 days |
| `cached_at`    | ISODate |                                           |

TTL: **7 days**.

### `cwe_impacts`

Unified document per CWE, containing both the technical-impact list and (optionally) full weakness info from the MITRE CWE REST API.

| Field               | Type     | Notes                                                 |
| ------------------- | -------- | ----------------------------------------------------- |
| `_id`               | string   | CWE ID, e.g. `CWE-502`                                |
| `technical_impacts` | [string] | Consensual matrix impact categories                   |
| `name`              | string   | Weakness name (populated by `get_cwe_info`)           |
| `description`       | string   | Weakness description (optional)                       |
| `source`            | string   | `"static"` (from in-code map) or `"rest"` (from MITRE API) |
| `cached_at`         | ISODate  |                                                       |

TTL: **30 days** (CWEs change rarely).

### `rebuild_jobs`

One document per rebuild invocation. Used to report progress back to the polling frontend.

| Field              | Type     | Notes                                                   |
| ------------------ | -------- | ------------------------------------------------------- |
| `_id`              | string   | UUID                                                    |
| `status`           | string   | `running` / `completed` / `failed` / `cancelled`        |
| `phase`            | string   | `loading` / `enriching_nvd` / `enriching_cwe` / `building_graph` / `done` |
| `started_at`       | ISODate  |                                                         |
| `completed_at`     | ISODate  | null while running                                      |
| `total_cves`       | int      | Count of unique CVEs in the scan (set during loading)   |
| `processed_cves`   | int      | Incremented per CVE                                     |
| `current_cve`      | string   | Most recent CVE the worker started processing           |
| `cancel_requested` | bool     | Worker checks between CVEs                              |
| `error`            | string   | On failure                                              |
| `stats`            | object   | Final graph stats on success                            |

**Invariant**: at most one document with `status = running` at a time. `JobManager.create_job()` enforces this.

---

## TTL Strategy — Soft, Not Index-Based

We could use a MongoDB TTL index to auto-delete stale docs after N seconds. We don't. Reasons:

1. **Auditability** — keeping stale records lets admin tools compare old vs new after a refresh (useful for debugging drift between the cached copy and the live NVD feed)
2. **No background cleaner surprises** — records only disappear when we explicitly call `clear_cache()`; they become "stale" but are still queryable
3. **Force-refresh is a backdate, not a delete** — `invalidate_collection(name)` sets all `cached_at` timestamps to epoch, causing the next read to re-fetch without ever losing a document

The check happens in `src/data/mongo_client.py`:

```python
def is_fresh(cached_at: Optional[datetime], ttl_days: int) -> bool:
    if cached_at is None:
        return False
    age = _utcnow() - _ensure_aware(cached_at)
    return age <= timedelta(days=ttl_days)
```

Callers use `cached_doc_if_fresh(collection, doc_id, ttl_days, force_refresh)` which returns `None` for missing, stale, or force-refresh'd documents and the document itself otherwise.

---

## Fail-Fast on Startup

`src/viz/app.py` calls `init_mongo()` during the FastAPI `startup` event. That function does a `ping` command with a 3-second server-selection timeout. If Mongo is unreachable, it raises `RuntimeError` with a user-friendly message pointing at `Scripts/start-mongo.sh`.

Bypass during isolated testing:

```bash
PAGDRAWER_SKIP_MONGO=1 python -m pytest tests/
```

(Tests that actually need Mongo depend on the `mock_mongo` fixture, which installs a `mongomock.MongoClient` as the singleton.)

---

## Background Rebuild Jobs

### Why a thread?

FastAPI is async, but our fetchers use blocking `urllib`. Running them directly in an async handler would:
- Block the event loop for the duration of the rebuild (minutes)
- Make progress polling unresponsive

Two options considered:
1. Migrate fetchers to `aiohttp` / `motor` — large refactor for marginal gain (NVD rate limit is the bottleneck, not concurrency)
2. Keep sync code, run worker on `threading.Thread` — minimal churn, event loop stays free

Chose option 2.

### Flow

```
1. Client: POST /api/data/rebuild
2. Handler creates a new rebuild_jobs document (status=running)
     → raises 409 Conflict if another job is already running
3. Handler schedules a FastAPI BackgroundTask that spawns a worker thread
4. Handler returns { "status": "started", "job_id": "<uuid>" }

5. Worker thread runs _run_rebuild_job():
     for each CVE:
        if JobManager.is_cancelled(job_id): raise CancelledError
        report progress to the job document
        fetch from NVD / CWE (with Mongo cache short-circuit)
     build the NetworkX graph
     JobManager.complete_job(stats=...)

6. Client polls GET /api/data/rebuild/progress/{job_id} every 500ms
7. Client renders phase + processed_cves / total_cves + current_cve
8. On terminal state (completed / failed / cancelled), client stops polling
```

### Cancel semantics

`POST /api/data/rebuild/cancel/{job_id}` sets `cancel_requested=true`. The worker checks this flag at the top of each CVE iteration. If a fetch is already in-flight (waiting on NVD's 6-second rate limiter), cancellation waits until that completes. Up-to-6-second lag, documented as a known limitation.

### Concurrency

One rebuild at a time. Intentional: the backend is a single-user dev tool, and parallel rebuilds would scramble the global graph state. Attempts return `409 Conflict` with the running job's ID in the error detail.

---

## NVDFetcher / CWEFetcher Call Paths

### NVD: single CVE lookup

```
fetch_cve(cve_id):
  if not force_refresh:
      doc = cached_doc_if_fresh(nvd_cves, cve_id, 7d)
      if doc and has epss: return doc
      if doc and missing epss: fetch_epss, upsert, return
  rate_limit_nvd()
  cve_data = _fetch_from_nvd(cve_id)  # urllib GET
  if fetch_epss: cve_data["epss_score"] = fetch_epss(cve_id)
  upsert_cached_doc(nvd_cves, cve_id, cve_data)
  return cve_data
```

### NVD: batch EPSS

`_batch_fetch_epss(cve_ids)` filters out already-fresh EPSS documents, then issues up to 30 CVEs per FIRST API call. Each batch response writes one upsert per CVE.

### CWE: impact lookup

```
get_technical_impacts(cwe_id):
  # Static short-circuit is CURRENTLY DISABLED (USE_STATIC_MAPPING = False)
  if USE_STATIC_MAPPING and cwe_id in STATIC_CWE_MAPPING:
      impacts = STATIC_CWE_MAPPING[cwe_id]
      if no cached doc yet: upsert with source="static"
      return impacts
  doc = cached_doc_if_fresh(cwe_impacts, cwe_id, 30d)
  if doc: return doc["technical_impacts"]
  if fetch_if_missing:
      impacts = _fetch_from_api(cwe_id)    # urllib GET cwe-api.mitre.org
      if impacts: upsert with source="rest"; return impacts
  # fallback: severity-based mapping (e.g. CRITICAL → "Execute Unauthorized Code")
  # or ultimate fallback: ["Other"]
```

**Note on `USE_STATIC_MAPPING`**: the in-code `STATIC_CWE_MAPPING` dict (~166 CWEs) is currently gated off. Every CWE encountered goes through Mongo / the MITRE REST API. This is a temporary choice until REST-sourced data has been validated against the in-code constant. See the TODO comment on `CWEFetcher.USE_STATIC_MAPPING`.

---

## Clearing / Refreshing Caches

Several levels of invalidation exist:

| Call                                     | Effect                                                   |
| ---------------------------------------- | -------------------------------------------------------- |
| `NVDFetcher(force_refresh=True).fetch_cve(id)` | Ignore cache for this fetcher instance            |
| `TrivyDataLoader(force_refresh=True).load()`  | Propagates into both fetchers                     |
| `invalidate_collection(name)`            | Backdate all `cached_at` in a collection                 |
| `NVDFetcher.clear_cache()`               | `delete_many({})` on nvd_cves + epss_scores              |
| `CWEFetcher.clear_cache()`               | `delete_many({})` on cwe_impacts                         |

The frontend currently exposes the per-rebuild force-refresh checkbox. A global "Refresh all" button in Settings was planned as Phase D and is deferred.

---

## Docker Compose

`docker-compose.yml` at the repo root defines one service:

```yaml
services:
  mongodb:
    image: mongo:7
    container_name: pagdrawer-mongo
    ports: ["27017:27017"]
    volumes: [mongodb_data:/data/db]
    command: ["mongod", "--wiredTigerCacheSizeGB", "0.5"]
volumes:
  mongodb_data:
    name: pagdrawer_mongodb_data
```

- No authentication — local dev only. Production deployments should set `MONGO_INITDB_ROOT_USERNAME` / `PASSWORD` and connect via a URI with credentials.
- Named volume means data persists across `docker-compose down` / kill-mongo.sh. Remove it manually with `docker volume rm pagdrawer_mongodb_data` for a clean slate.
- WiredTiger cache capped at 512 MB so the container doesn't hog laptop RAM.

---

## Testing Story

| Test file                  | Purpose                                                    |
| -------------------------- | ---------------------------------------------------------- |
| `tests/test_mongo_client.py` | TTL helpers, singleton lifecycle (16 tests, mongomock)   |
| `tests/test_jobs.py`         | JobManager lifecycle (17 tests, mongomock)               |
| `tests/test_nvd_fetcher.py`  | Fetcher with mongomock + mocked urlopen (24 tests)       |
| `tests/test_cwe_fetcher.py`  | Same pattern, plus static-mode / disabled-mode coverage (48 tests) |
| `tests/test_api_endpoints.py`| rebuild endpoint returns job_id; 409 conflict; progress/cancel endpoints |

The shared `mock_mongo` fixture in `tests/conftest.py` installs `mongomock.MongoClient()` as the singleton for one test. No real MongoDB needed for CI.

---

## Operational Notes

### First rebuild is slow

NVD rate limits at 6 seconds per request without an API key. For a 200-CVE scan, that's roughly 20 minutes. The progress bar makes this tolerable; subsequent rebuilds of the same scan complete in seconds (Mongo hit).

Get an NVD API key and set `NVD_API_KEY` env var (not yet wired to config) for higher limits.

### Observing the cache

From mongosh:

```bash
docker exec -it pagdrawer-mongo mongosh pagdrawer --eval 'db.nvd_cves.countDocuments({})'
docker exec -it pagdrawer-mongo mongosh pagdrawer --eval 'db.cwe_impacts.find({source: "rest"})'
```

Or point a GUI client at `mongodb://localhost:27017`.

### Dead jobs

If a rebuild crashes outside `JobManager` (e.g. backend hard-kill), the document stays `status=running` and blocks future rebuilds. `JobManager.purge_old_jobs(older_than_seconds=3600)` clears these; could be called on startup. Not currently auto-invoked — manual cleanup for now:

```python
from src.data.jobs import JobManager
from src.data.mongo_client import init_mongo
init_mongo()
JobManager().purge_old_jobs(0)  # purge all completed/failed/cancelled
```

---

## Deferred Work

- **Phase D**: global "Refresh all NVD data" button in Settings
- **Re-enable `USE_STATIC_MAPPING`** after REST-data validation
- **Auto-purge jobs on startup** (`JobManager.purge_old_jobs(3600)` in the FastAPI startup event)
- **NVD API key wiring** through config / env var for higher rate limits
- **Offline/read-only mode** — currently, Mongo is hard-required; a fallback mode could serve cached data even if Mongo is down
