"""
Tests for src/data/mongo_client.py TTL helpers and singleton lifecycle.

We use mongomock so the suite runs without a live Mongo instance.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import mongomock

from src.data import mongo_client as mc


@pytest.fixture
def mock_db():
    """Reset the singleton between tests and replace the client with mongomock."""
    mc.close_mongo()
    fake_client = mongomock.MongoClient()
    mc._client = fake_client
    mc._db = fake_client[mc.DEFAULT_DB_NAME]
    yield mc._db
    mc.close_mongo()


class TestIsFresh:
    def test_returns_false_for_none(self):
        assert mc.is_fresh(None, ttl_days=7) is False

    def test_returns_true_for_recent(self):
        recent = datetime.now(timezone.utc) - timedelta(hours=1)
        assert mc.is_fresh(recent, ttl_days=7) is True

    def test_returns_false_for_expired(self):
        expired = datetime.now(timezone.utc) - timedelta(days=8)
        assert mc.is_fresh(expired, ttl_days=7) is False

    def test_boundary_within_ttl(self):
        just_under = datetime.now(timezone.utc) - timedelta(days=7) + timedelta(seconds=1)
        assert mc.is_fresh(just_under, ttl_days=7) is True

    def test_boundary_exactly_ttl(self):
        # At the exact boundary we consider the record fresh (<=).
        exact = datetime.now(timezone.utc) - timedelta(days=7) + timedelta(milliseconds=100)
        assert mc.is_fresh(exact, ttl_days=7) is True

    def test_naive_datetime_treated_as_utc(self):
        # pymongo may return naive UTC datetimes; we must not crash.
        naive = datetime.utcnow() - timedelta(hours=1)
        assert mc.is_fresh(naive, ttl_days=7) is True


class TestCachedDocIfFresh:
    def test_returns_none_when_doc_missing(self, mock_db):
        assert mc.cached_doc_if_fresh("nvd_cves", "CVE-9999", ttl_days=7) is None

    def test_returns_doc_when_fresh(self, mock_db):
        mock_db.nvd_cves.insert_one({
            "_id": "CVE-1",
            "cached_at": datetime.now(timezone.utc) - timedelta(hours=1),
            "payload": "fresh"
        })
        doc = mc.cached_doc_if_fresh("nvd_cves", "CVE-1", ttl_days=7)
        assert doc is not None
        assert doc["payload"] == "fresh"

    def test_returns_none_when_stale(self, mock_db):
        mock_db.nvd_cves.insert_one({
            "_id": "CVE-2",
            "cached_at": datetime.now(timezone.utc) - timedelta(days=30),
            "payload": "stale"
        })
        assert mc.cached_doc_if_fresh("nvd_cves", "CVE-2", ttl_days=7) is None

    def test_force_refresh_returns_none_even_if_fresh(self, mock_db):
        mock_db.nvd_cves.insert_one({
            "_id": "CVE-3",
            "cached_at": datetime.now(timezone.utc),
            "payload": "fresh"
        })
        assert mc.cached_doc_if_fresh("nvd_cves", "CVE-3", ttl_days=7, force_refresh=True) is None


class TestUpsertCachedDoc:
    def test_inserts_new_doc_with_timestamp(self, mock_db):
        mc.upsert_cached_doc("nvd_cves", "CVE-X", {"field": "value"})
        doc = mock_db.nvd_cves.find_one({"_id": "CVE-X"})
        assert doc is not None
        assert doc["field"] == "value"
        assert "cached_at" in doc

    def test_upsert_replaces_existing_fields(self, mock_db):
        mc.upsert_cached_doc("nvd_cves", "CVE-Y", {"field": "v1"})
        mc.upsert_cached_doc("nvd_cves", "CVE-Y", {"field": "v2"})
        doc = mock_db.nvd_cves.find_one({"_id": "CVE-Y"})
        assert doc["field"] == "v2"

    def test_cached_at_is_updated_on_re_upsert(self, mock_db):
        frozen = datetime(2020, 1, 1, tzinfo=timezone.utc)
        with patch.object(mc, "_utcnow", return_value=frozen):
            mc.upsert_cached_doc("nvd_cves", "CVE-Z", {"field": "old"})
        old_doc = mock_db.nvd_cves.find_one({"_id": "CVE-Z"})
        assert old_doc["cached_at"].replace(tzinfo=timezone.utc) == frozen

        newer = datetime(2024, 1, 1, tzinfo=timezone.utc)
        with patch.object(mc, "_utcnow", return_value=newer):
            mc.upsert_cached_doc("nvd_cves", "CVE-Z", {"field": "new"})
        new_doc = mock_db.nvd_cves.find_one({"_id": "CVE-Z"})
        assert new_doc["cached_at"].replace(tzinfo=timezone.utc) == newer


class TestInvalidateCollection:
    def test_backdates_all_cached_at(self, mock_db):
        now = datetime.now(timezone.utc)
        mock_db.nvd_cves.insert_many([
            {"_id": "CVE-A", "cached_at": now},
            {"_id": "CVE-B", "cached_at": now},
            {"_id": "CVE-C", "cached_at": now},
        ])

        modified = mc.invalidate_collection("nvd_cves")
        assert modified == 3

        for doc in mock_db.nvd_cves.find():
            # All cached_at should be in the distant past and therefore stale.
            assert not mc.is_fresh(doc["cached_at"], ttl_days=7)

    def test_invalidate_empty_collection_returns_zero(self, mock_db):
        assert mc.invalidate_collection("nvd_cves") == 0


class TestGetDbRequiresInit:
    def test_raises_when_not_initialized(self):
        mc.close_mongo()
        with pytest.raises(RuntimeError, match="not been initialized"):
            mc.get_db()
