"""
Tests for NVD Fetcher.

Uses mocked urlopen to avoid network calls and mongomock (via the
`mock_mongo` fixture in conftest.py) to back the cache in memory.
"""

import json
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from src.data.loaders.nvd_fetcher import (
    NVDFetcher,
    fetch_cve,
    fetch_epss,
    enrich_cve,
    NVD_API_URL,
    EPSS_API_URL,
    CACHE_TTL_DAYS,
)
from src.data.mongo_client import (
    COLLECTION_NVD_CVES,
    COLLECTION_EPSS,
    upsert_cached_doc,
)


# Sample NVD API response for CVE-2021-44228 (Log4Shell)
SAMPLE_NVD_RESPONSE = {
    "vulnerabilities": [
        {
            "cve": {
                "id": "CVE-2021-44228",
                "descriptions": [
                    {
                        "lang": "en",
                        "value": "Apache Log4j2 2.0-beta9 through 2.15.0 JNDI features do not protect against attacker controlled LDAP and other JNDI related endpoints."
                    }
                ],
                "metrics": {
                    "cvssMetricV31": [
                        {
                            "cvssData": {
                                "vectorString": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
                                "baseScore": 10.0,
                                "baseSeverity": "CRITICAL"
                            }
                        }
                    ]
                },
                "weaknesses": [
                    {
                        "description": [
                            {"value": "CWE-502"},
                            {"value": "CWE-400"}
                        ]
                    }
                ],
                "published": "2021-12-10T10:15:00.000",
                "lastModified": "2023-04-03T20:15:00.000",
                "references": [
                    {"url": "https://logging.apache.org/log4j/2.x/security.html", "source": "apache"}
                ]
            }
        }
    ]
}

SAMPLE_EPSS_RESPONSE = {
    "data": [
        {
            "cve": "CVE-2021-44228",
            "epss": "0.97565",
            "percentile": "0.99996"
        }
    ]
}


class TestNVDFetcherInit:
    """Tests for NVDFetcher initialization."""

    def test_default_force_refresh_is_false(self, mock_mongo):
        fetcher = NVDFetcher()
        assert fetcher.force_refresh is False

    def test_force_refresh_flag_honored(self, mock_mongo):
        fetcher = NVDFetcher(force_refresh=True)
        assert fetcher.force_refresh is True


class TestParseCVEItem:
    """Tests for parsing NVD CVE items (pure parsing, no cache)."""

    @pytest.fixture
    def fetcher(self, mock_mongo):
        return NVDFetcher()

    def test_parse_cve_id(self, fetcher):
        cve_item = SAMPLE_NVD_RESPONSE["vulnerabilities"][0]["cve"]
        result = fetcher._parse_cve_item(cve_item)
        assert result["id"] == "CVE-2021-44228"

    def test_parse_description(self, fetcher):
        cve_item = SAMPLE_NVD_RESPONSE["vulnerabilities"][0]["cve"]
        result = fetcher._parse_cve_item(cve_item)
        assert "Log4j" in result["description"]
        assert "JNDI" in result["description"]

    def test_parse_cvss_v31(self, fetcher):
        cve_item = SAMPLE_NVD_RESPONSE["vulnerabilities"][0]["cve"]
        result = fetcher._parse_cve_item(cve_item)
        assert result["cvss_vector"] == "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
        assert result["cvss_score"] == 10.0
        assert result["severity"] == "CRITICAL"

    def test_parse_cwe_ids(self, fetcher):
        cve_item = SAMPLE_NVD_RESPONSE["vulnerabilities"][0]["cve"]
        result = fetcher._parse_cve_item(cve_item)
        assert "CWE-502" in result["cwe_ids"]
        assert "CWE-400" in result["cwe_ids"]

    def test_parse_dates(self, fetcher):
        cve_item = SAMPLE_NVD_RESPONSE["vulnerabilities"][0]["cve"]
        result = fetcher._parse_cve_item(cve_item)
        assert "2021-12-10" in result["published"]
        assert result["modified"] != ""

    def test_parse_cvss_v30_fallback(self, fetcher):
        cve_item = {
            "id": "CVE-TEST",
            "descriptions": [{"lang": "en", "value": "Test"}],
            "metrics": {
                "cvssMetricV30": [
                    {
                        "cvssData": {
                            "vectorString": "CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                            "baseScore": 9.8,
                            "baseSeverity": "CRITICAL"
                        }
                    }
                ]
            },
            "weaknesses": [],
        }
        result = fetcher._parse_cve_item(cve_item)
        assert "CVSS:3.0" in result["cvss_vector"]
        assert result["cvss_score"] == 9.8


class TestFetchCVE:
    """Tests for fetching CVE data from NVD."""

    @pytest.fixture
    def fetcher(self, mock_mongo):
        return NVDFetcher()

    def test_fetch_cve_uses_cache(self, mock_mongo, fetcher):
        """Should return cached data without network request."""
        upsert_cached_doc(COLLECTION_NVD_CVES, "CVE-2021-44228", {
            "id": "CVE-2021-44228",
            "description": "Cached description",
        })
        result = fetcher.fetch_cve("CVE-2021-44228", fetch_epss=False)
        assert result is not None
        assert result["description"] == "Cached description"

    @patch("src.data.loaders.nvd_fetcher.urlopen")
    def test_fetch_cve_from_api(self, mock_urlopen, mock_mongo, fetcher):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(SAMPLE_NVD_RESPONSE).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = fetcher.fetch_cve("CVE-2021-44228", use_cache=False, fetch_epss=False)
        assert result is not None
        assert result["id"] == "CVE-2021-44228"
        assert "Log4j" in result["description"]

    @patch("src.data.loaders.nvd_fetcher.urlopen")
    def test_fetch_cve_caches_result_to_mongo(self, mock_urlopen, mock_mongo, fetcher):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(SAMPLE_NVD_RESPONSE).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        fetcher.fetch_cve("CVE-2021-44228", use_cache=False, fetch_epss=False)
        doc = mock_mongo[COLLECTION_NVD_CVES].find_one({"_id": "CVE-2021-44228"})
        assert doc is not None
        assert doc["id"] == "CVE-2021-44228"

    def test_force_refresh_bypasses_cache(self, mock_mongo):
        """Force refresh should cause refetch even if cache is fresh."""
        upsert_cached_doc(COLLECTION_NVD_CVES, "CVE-X", {"description": "Cached"})
        fetcher = NVDFetcher(force_refresh=True)
        # force_refresh short-circuits cache; the next step would be a network call,
        # but we skip it here by verifying that the in-cache document isn't returned.
        with patch("src.data.loaders.nvd_fetcher.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = Exception("network should not be called")
            # It's fine to raise — we're only validating we don't return the cached doc.
            with pytest.raises(Exception):
                fetcher.fetch_cve("CVE-X", fetch_epss=False)


class TestFetchEPSS:
    """Tests for fetching EPSS scores."""

    @pytest.fixture
    def fetcher(self, mock_mongo):
        return NVDFetcher()

    def test_fetch_epss_uses_cache(self, mock_mongo, fetcher):
        upsert_cached_doc(COLLECTION_EPSS, "CVE-2021-44228", {"epss_score": 0.975})
        result = fetcher.fetch_epss("CVE-2021-44228")
        assert result == 0.975

    @patch("src.data.loaders.nvd_fetcher.urlopen")
    def test_fetch_epss_from_api(self, mock_urlopen, mock_mongo, fetcher):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(SAMPLE_EPSS_RESPONSE).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = fetcher.fetch_epss("CVE-2021-44228", use_cache=False)
        assert result is not None
        assert result > 0.9

    @patch("src.data.loaders.nvd_fetcher.urlopen")
    def test_fetch_epss_caches_result_to_mongo(self, mock_urlopen, mock_mongo, fetcher):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(SAMPLE_EPSS_RESPONSE).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        fetcher.fetch_epss("CVE-2021-44228", use_cache=False)
        doc = mock_mongo[COLLECTION_EPSS].find_one({"_id": "CVE-2021-44228"})
        assert doc is not None
        assert doc["epss_score"] == pytest.approx(0.97565, abs=0.01)


class TestEnrichCVE:
    """Tests for CVE data enrichment."""

    @pytest.fixture
    def fetcher(self, mock_mongo):
        return NVDFetcher()

    def test_enrich_fills_missing_description(self, mock_mongo, fetcher):
        upsert_cached_doc(COLLECTION_NVD_CVES, "CVE-2021-44228", {
            "id": "CVE-2021-44228",
            "description": "NVD description",
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
            "severity": "CRITICAL",
            "cwe_ids": ["CWE-502"],
        })
        cve_data = {"id": "CVE-2021-44228"}
        enriched = fetcher.enrich_cve_data(cve_data, fetch_if_missing=False)
        assert enriched["description"] == "NVD description"

    def test_enrich_fills_missing_cvss(self, mock_mongo, fetcher):
        upsert_cached_doc(COLLECTION_NVD_CVES, "CVE-2021-44228", {
            "id": "CVE-2021-44228",
            "description": "Test",
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
        })
        cve_data = {"id": "CVE-2021-44228", "description": "Existing desc"}
        enriched = fetcher.enrich_cve_data(cve_data, fetch_if_missing=False)
        assert enriched["cvss_vector"] == "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
        assert enriched["description"] == "Existing desc"

    def test_enrich_preserves_existing_data(self, mock_mongo, fetcher):
        upsert_cached_doc(COLLECTION_NVD_CVES, "CVE-2021-44228", {
            "id": "CVE-2021-44228",
            "description": "NVD description",
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
        })
        cve_data = {
            "id": "CVE-2021-44228",
            "description": "My description",
            "cvss_vector": "CVSS:3.1/AV:L/AC:H/PR:H/UI:R/S:U/C:L/I:L/A:L",
        }
        enriched = fetcher.enrich_cve_data(cve_data, fetch_if_missing=False)
        assert enriched["description"] == "My description"
        assert enriched["cvss_vector"] == "CVSS:3.1/AV:L/AC:H/PR:H/UI:R/S:U/C:L/I:L/A:L"


class TestBatchFetchEPSS:
    """Tests for batch EPSS fetching."""

    @pytest.fixture
    def fetcher(self, mock_mongo):
        return NVDFetcher()

    @patch("src.data.loaders.nvd_fetcher.urlopen")
    def test_batch_fetch_multiple_cves(self, mock_urlopen, mock_mongo, fetcher):
        batch_response = {
            "data": [
                {"cve": "CVE-2021-44228", "epss": "0.975"},
                {"cve": "CVE-2021-45046", "epss": "0.85"},
            ]
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(batch_response).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        fetcher._batch_fetch_epss(["CVE-2021-44228", "CVE-2021-45046"], use_cache=False)

        assert mock_mongo[COLLECTION_EPSS].find_one({"_id": "CVE-2021-44228"}) is not None
        assert mock_mongo[COLLECTION_EPSS].find_one({"_id": "CVE-2021-45046"}) is not None


class TestClearCache:
    """Tests for cache clearing."""

    def test_clear_cache_removes_all_docs(self, mock_mongo):
        fetcher = NVDFetcher()
        upsert_cached_doc(COLLECTION_NVD_CVES, "CVE-A", {"x": 1})
        upsert_cached_doc(COLLECTION_EPSS, "CVE-A", {"epss_score": 0.5})

        fetcher.clear_cache()

        assert mock_mongo[COLLECTION_NVD_CVES].count_documents({}) == 0
        assert mock_mongo[COLLECTION_EPSS].count_documents({}) == 0


class TestCacheStats:
    """Tests for cache statistics."""

    def test_get_cache_stats_reports_mongo_counts(self, mock_mongo):
        fetcher = NVDFetcher()
        upsert_cached_doc(COLLECTION_NVD_CVES, "CVE-1", {})
        upsert_cached_doc(COLLECTION_NVD_CVES, "CVE-2", {})
        upsert_cached_doc(COLLECTION_EPSS, "CVE-1", {"epss_score": 0.1})

        stats = fetcher.get_cache_stats()
        assert stats["nvd_entries"] == 2
        assert stats["epss_entries"] == 1


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_fetch_cve_function_exists(self):
        from src.data.loaders.nvd_fetcher import fetch_cve
        assert callable(fetch_cve)

    def test_fetch_epss_function_exists(self):
        from src.data.loaders.nvd_fetcher import fetch_epss
        assert callable(fetch_epss)

    def test_enrich_cve_function_exists(self):
        from src.data.loaders.nvd_fetcher import enrich_cve
        assert callable(enrich_cve)
