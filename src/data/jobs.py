"""
Rebuild job manager — tracks progress of long-running graph rebuilds so
the frontend can poll for status and display a progress bar.

Jobs live in the `rebuild_jobs` MongoDB collection. Exactly one job may
be in the "running" state at a time; attempts to start another return
a conflict. Completed/failed jobs stay in the collection for a short
window so the polling client can observe the terminal state.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.data.mongo_client import (
    COLLECTION_REBUILD_JOBS,
    get_db,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Status constants
# =============================================================================

STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

#: Phases we report during a rebuild. More can be added without schema change.
PHASE_LOADING = "loading"           # Parsing Trivy JSON, collecting CVE IDs
PHASE_NVD = "enriching_nvd"         # Fetching CVE details from NVD
PHASE_CWE = "enriching_cwe"         # Fetching technical impacts from MITRE CWE
PHASE_BUILDING = "building_graph"   # Building the NetworkX graph
PHASE_DONE = "done"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RebuildJob:
    """In-memory view of a rebuild job document."""
    job_id: str
    status: str
    started_at: datetime
    phase: str = PHASE_LOADING
    current_cve: Optional[str] = None
    processed_cves: int = 0
    total_cves: int = 0
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
    cancel_requested: bool = False

    def to_doc(self) -> Dict[str, Any]:
        """Serialize to a Mongo-friendly dict."""
        return {
            "_id": self.job_id,
            "status": self.status,
            "started_at": self.started_at,
            "phase": self.phase,
            "current_cve": self.current_cve,
            "processed_cves": self.processed_cves,
            "total_cves": self.total_cves,
            "completed_at": self.completed_at,
            "error": self.error,
            "stats": self.stats,
            "cancel_requested": self.cancel_requested,
        }

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "RebuildJob":
        return cls(
            job_id=doc["_id"],
            status=doc["status"],
            started_at=doc["started_at"],
            phase=doc.get("phase", PHASE_LOADING),
            current_cve=doc.get("current_cve"),
            processed_cves=doc.get("processed_cves", 0),
            total_cves=doc.get("total_cves", 0),
            completed_at=doc.get("completed_at"),
            error=doc.get("error"),
            stats=doc.get("stats"),
            cancel_requested=doc.get("cancel_requested", False),
        )


class JobExistsError(RuntimeError):
    """Raised when attempting to start a second concurrent rebuild job."""


class JobManager:
    """Thin DAO for rebuild job documents.

    All methods are synchronous (pymongo) — callers in async code should
    wrap them with asyncio.to_thread if they must not block the event loop.
    """

    def __init__(self, collection_name: str = COLLECTION_REBUILD_JOBS):
        self._collection_name = collection_name

    @property
    def _collection(self):
        return get_db()[self._collection_name]

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def create_job(self, total_cves: int = 0) -> RebuildJob:
        """Start a new rebuild job. Raises JobExistsError if one is running."""
        if self._collection.find_one({"status": STATUS_RUNNING}) is not None:
            raise JobExistsError("Another rebuild job is already running.")

        job = RebuildJob(
            job_id=str(uuid.uuid4()),
            status=STATUS_RUNNING,
            started_at=_utcnow(),
            total_cves=total_cves,
        )
        self._collection.insert_one(job.to_doc())
        logger.info(f"Started rebuild job {job.job_id} (total_cves={total_cves})")
        return job

    def get_job(self, job_id: str) -> Optional[RebuildJob]:
        doc = self._collection.find_one({"_id": job_id})
        return RebuildJob.from_doc(doc) if doc else None

    def get_running_job(self) -> Optional[RebuildJob]:
        doc = self._collection.find_one({"status": STATUS_RUNNING})
        return RebuildJob.from_doc(doc) if doc else None

    # -------------------------------------------------------------------------
    # Progress updates
    # -------------------------------------------------------------------------

    def update_progress(
        self,
        job_id: str,
        *,
        processed_cves: Optional[int] = None,
        current_cve: Optional[str] = None,
        phase: Optional[str] = None,
        total_cves: Optional[int] = None,
    ) -> None:
        """Partial update. Fields left None are not modified."""
        update: Dict[str, Any] = {}
        if processed_cves is not None:
            update["processed_cves"] = processed_cves
        if current_cve is not None:
            update["current_cve"] = current_cve
        if phase is not None:
            update["phase"] = phase
        if total_cves is not None:
            update["total_cves"] = total_cves
        if not update:
            return
        self._collection.update_one({"_id": job_id}, {"$set": update})

    # -------------------------------------------------------------------------
    # Terminal states
    # -------------------------------------------------------------------------

    def complete_job(self, job_id: str, stats: Optional[Dict[str, Any]] = None) -> None:
        self._collection.update_one(
            {"_id": job_id},
            {"$set": {
                "status": STATUS_COMPLETED,
                "phase": PHASE_DONE,
                "completed_at": _utcnow(),
                "stats": stats,
            }},
        )
        logger.info(f"Rebuild job {job_id} completed")

    def fail_job(self, job_id: str, error: str) -> None:
        self._collection.update_one(
            {"_id": job_id},
            {"$set": {
                "status": STATUS_FAILED,
                "completed_at": _utcnow(),
                "error": error,
            }},
        )
        logger.warning(f"Rebuild job {job_id} failed: {error}")

    def request_cancel(self, job_id: str) -> bool:
        """Flip the cancel_requested flag. Returns True if the job was running."""
        result = self._collection.update_one(
            {"_id": job_id, "status": STATUS_RUNNING},
            {"$set": {"cancel_requested": True}},
        )
        return result.modified_count > 0

    def cancel_finalize(self, job_id: str) -> None:
        """Mark a cancelled job as terminally cancelled (called from the worker
        after it notices cancel_requested)."""
        self._collection.update_one(
            {"_id": job_id},
            {"$set": {
                "status": STATUS_CANCELLED,
                "completed_at": _utcnow(),
            }},
        )
        logger.info(f"Rebuild job {job_id} cancelled")

    def is_cancelled(self, job_id: str) -> bool:
        """True if the worker should stop at the next checkpoint."""
        doc = self._collection.find_one(
            {"_id": job_id},
            projection={"cancel_requested": 1},
        )
        return bool(doc and doc.get("cancel_requested"))

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    def purge_old_jobs(self, older_than_seconds: int = 3600) -> int:
        """Delete jobs that completed more than N seconds ago.

        Call this periodically (e.g. on app startup or before create_job).
        Returns the number of documents removed.
        """
        cutoff = _utcnow()
        cutoff = cutoff.replace(microsecond=0) - _td(older_than_seconds)
        result = self._collection.delete_many({
            "status": {"$in": [STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED]},
            "completed_at": {"$lt": cutoff},
        })
        return result.deleted_count


def _td(seconds: int):
    """Small helper: timedelta. Kept local to avoid leaking symbols."""
    from datetime import timedelta
    return timedelta(seconds=seconds)
