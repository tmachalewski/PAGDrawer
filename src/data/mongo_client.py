"""
MongoDB client singleton and TTL-aware cache helpers for PAGDrawer.

Why a singleton? The backend is a single-process FastAPI app; a shared
pymongo client owns a connection pool and should not be reinstantiated
per request.

TTL strategy: we store `cached_at` as an ISO datetime on each document
and check it in Python when reading. We do NOT use MongoDB's TTL index
to auto-delete, so stale records remain queryable and a "force refresh"
operation can simply backdate `cached_at` without losing data.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError


# =============================================================================
# Configuration
# =============================================================================

#: Default connection URI; override with MONGODB_URI env var.
DEFAULT_MONGODB_URI = "mongodb://localhost:27017"

#: Database name used by PAGDrawer.
DEFAULT_DB_NAME = "pagdrawer"

#: Collection names. Exported for consistent use across fetchers.
COLLECTION_NVD_CVES = "nvd_cves"
COLLECTION_EPSS = "epss_scores"
COLLECTION_CWE_IMPACTS = "cwe_impacts"
COLLECTION_REBUILD_JOBS = "rebuild_jobs"

#: Default TTLs (soft — checked in code, not enforced by Mongo TTL index).
TTL_NVD_DAYS = 7
TTL_EPSS_DAYS = 7
TTL_CWE_DAYS = 30


# =============================================================================
# Singleton state
# =============================================================================

_client: Optional[MongoClient] = None
_db: Optional[Database] = None


def _build_client(uri: str, timeout_ms: int = 3000) -> MongoClient:
    """Construct a MongoClient with a short server-selection timeout so that
    `ping()` fails fast if Mongo is unreachable."""
    return MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)


def init_mongo(uri: Optional[str] = None, db_name: Optional[str] = None) -> Database:
    """Initialize the singleton client + database and verify reachability.

    Raises:
        RuntimeError: if MongoDB cannot be reached. The message is user-friendly
        and includes remediation guidance (start Scripts/start-mongo.sh).
    """
    global _client, _db
    resolved_uri = uri or os.environ.get("MONGODB_URI", DEFAULT_MONGODB_URI)
    resolved_db_name = db_name or os.environ.get("MONGODB_DB", DEFAULT_DB_NAME)

    try:
        _client = _build_client(resolved_uri)
        # Force the driver to open a connection and raise if unreachable.
        _client.admin.command("ping")
    except (ServerSelectionTimeoutError, PyMongoError) as e:
        raise RuntimeError(
            f"Could not connect to MongoDB at {resolved_uri}. "
            f"Start it with 'bash Scripts/start-mongo.sh'. Original error: {e}"
        ) from e

    _db = _client[resolved_db_name]
    return _db


def get_db() -> Database:
    """Return the initialized database. Raises if init_mongo was not called."""
    if _db is None:
        raise RuntimeError("MongoDB has not been initialized. Call init_mongo() first.")
    return _db


def close_mongo() -> None:
    """Close the singleton client. Primarily for tests."""
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None


# =============================================================================
# TTL helpers
# =============================================================================

def _utcnow() -> datetime:
    """Timezone-aware UTC now. Kept as a helper so tests can monkeypatch it."""
    return datetime.now(timezone.utc)


def _ensure_aware(dt: datetime) -> datetime:
    """Treat naive datetimes as UTC (pymongo may return naive BSON datetimes)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def is_fresh(cached_at: Optional[datetime], ttl_days: int) -> bool:
    """Return True if cached_at is within ttl_days of now.

    None or missing timestamps always count as stale.
    """
    if cached_at is None:
        return False
    age = _utcnow() - _ensure_aware(cached_at)
    return age <= timedelta(days=ttl_days)


def cached_doc_if_fresh(
    collection_name: str,
    doc_id: str,
    ttl_days: int,
    force_refresh: bool = False,
) -> Optional[Dict[str, Any]]:
    """Read a document by _id and return it only if within TTL.

    Returns None if the document is missing, stale, or if force_refresh is set.
    """
    if force_refresh:
        return None
    doc = get_db()[collection_name].find_one({"_id": doc_id})
    if doc is None:
        return None
    if not is_fresh(doc.get("cached_at"), ttl_days):
        return None
    return doc


def upsert_cached_doc(
    collection_name: str,
    doc_id: str,
    payload: Dict[str, Any],
) -> None:
    """Upsert a cache document with a fresh cached_at timestamp.

    The caller provides the payload minus `_id` and `cached_at`; this function
    adds both.
    """
    to_write = dict(payload)
    to_write["cached_at"] = _utcnow()
    get_db()[collection_name].update_one(
        {"_id": doc_id},
        {"$set": to_write},
        upsert=True,
    )


def invalidate_collection(collection_name: str) -> int:
    """Backdate cached_at on all docs in a collection so they count as stale.

    Used by the global "Force refresh" button. Returns the number of docs
    touched. Does not delete anything — stale records remain available for
    diff / audit after a re-fetch.
    """
    far_past = datetime(1970, 1, 1, tzinfo=timezone.utc)
    result = get_db()[collection_name].update_many(
        {},
        {"$set": {"cached_at": far_past}},
    )
    return result.modified_count
