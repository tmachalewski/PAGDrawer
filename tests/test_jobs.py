"""Tests for src/data/jobs.py (rebuild job manager)."""

from datetime import datetime, timedelta, timezone

import pytest

from src.data.jobs import (
    JobManager,
    JobExistsError,
    RebuildJob,
    STATUS_RUNNING,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_CANCELLED,
    PHASE_NVD,
    PHASE_CWE,
    PHASE_BUILDING,
    PHASE_DONE,
)
from src.data.mongo_client import COLLECTION_REBUILD_JOBS


@pytest.fixture
def jm(mock_mongo):
    return JobManager()


class TestCreateJob:
    def test_returns_running_job_with_uuid(self, jm):
        job = jm.create_job(total_cves=42)
        assert job.status == STATUS_RUNNING
        assert job.total_cves == 42
        assert len(job.job_id) > 0

    def test_persists_to_mongo(self, mock_mongo, jm):
        job = jm.create_job(total_cves=5)
        doc = mock_mongo[COLLECTION_REBUILD_JOBS].find_one({"_id": job.job_id})
        assert doc is not None
        assert doc["status"] == STATUS_RUNNING

    def test_rejects_when_another_is_running(self, jm):
        jm.create_job()
        with pytest.raises(JobExistsError):
            jm.create_job()

    def test_allows_new_after_previous_completed(self, jm):
        job1 = jm.create_job()
        jm.complete_job(job1.job_id)
        job2 = jm.create_job()  # should not raise
        assert job2.job_id != job1.job_id


class TestUpdateProgress:
    def test_updates_only_specified_fields(self, mock_mongo, jm):
        job = jm.create_job(total_cves=100)
        jm.update_progress(job.job_id, processed_cves=10, current_cve="CVE-X")
        updated = jm.get_job(job.job_id)
        assert updated.processed_cves == 10
        assert updated.current_cve == "CVE-X"
        assert updated.total_cves == 100  # not clobbered

    def test_phase_update(self, jm):
        job = jm.create_job()
        jm.update_progress(job.job_id, phase=PHASE_CWE)
        assert jm.get_job(job.job_id).phase == PHASE_CWE

    def test_noop_when_all_none(self, jm):
        job = jm.create_job()
        jm.update_progress(job.job_id)  # all None
        # Should not raise and leave job unchanged
        assert jm.get_job(job.job_id).status == STATUS_RUNNING


class TestTerminalStates:
    def test_complete_sets_stats_and_status(self, jm):
        job = jm.create_job()
        jm.complete_job(job.job_id, stats={"total_nodes": 400})
        completed = jm.get_job(job.job_id)
        assert completed.status == STATUS_COMPLETED
        assert completed.phase == PHASE_DONE
        assert completed.stats == {"total_nodes": 400}
        assert completed.completed_at is not None

    def test_fail_sets_error(self, jm):
        job = jm.create_job()
        jm.fail_job(job.job_id, error="NVD timeout")
        failed = jm.get_job(job.job_id)
        assert failed.status == STATUS_FAILED
        assert failed.error == "NVD timeout"


class TestCancellation:
    def test_request_cancel_returns_true_when_running(self, jm):
        job = jm.create_job()
        assert jm.request_cancel(job.job_id) is True
        assert jm.is_cancelled(job.job_id) is True

    def test_request_cancel_returns_false_when_not_running(self, jm):
        job = jm.create_job()
        jm.complete_job(job.job_id)
        assert jm.request_cancel(job.job_id) is False

    def test_cancel_finalize_sets_cancelled_status(self, jm):
        job = jm.create_job()
        jm.request_cancel(job.job_id)
        jm.cancel_finalize(job.job_id)
        assert jm.get_job(job.job_id).status == STATUS_CANCELLED

    def test_is_cancelled_false_on_unknown_job(self, jm):
        assert jm.is_cancelled("nonexistent") is False


class TestPurgeOldJobs:
    def test_removes_completed_jobs_older_than_cutoff(self, mock_mongo, jm):
        # Insert a job that completed 2 hours ago
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        mock_mongo[COLLECTION_REBUILD_JOBS].insert_one({
            "_id": "old",
            "status": STATUS_COMPLETED,
            "started_at": old_time,
            "completed_at": old_time,
        })
        # Insert one that completed 5 minutes ago
        recent = datetime.now(timezone.utc) - timedelta(minutes=5)
        mock_mongo[COLLECTION_REBUILD_JOBS].insert_one({
            "_id": "recent",
            "status": STATUS_COMPLETED,
            "started_at": recent,
            "completed_at": recent,
        })

        deleted = jm.purge_old_jobs(older_than_seconds=3600)
        assert deleted == 1
        assert jm.get_job("old") is None
        assert jm.get_job("recent") is not None

    def test_does_not_purge_running_jobs(self, mock_mongo, jm):
        old_time = datetime.now(timezone.utc) - timedelta(hours=5)
        mock_mongo[COLLECTION_REBUILD_JOBS].insert_one({
            "_id": "zombie",
            "status": STATUS_RUNNING,
            "started_at": old_time,
        })
        jm.purge_old_jobs(older_than_seconds=3600)
        assert jm.get_job("zombie") is not None


class TestGetJob:
    def test_returns_none_for_unknown(self, jm):
        assert jm.get_job("nope") is None

    def test_get_running_returns_running_or_none(self, jm):
        assert jm.get_running_job() is None
        job = jm.create_job()
        running = jm.get_running_job()
        assert running is not None
        assert running.job_id == job.job_id
