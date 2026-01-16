"""
Tests for NVD Fetcher.

Tests the NVD and EPSS data fetching, caching, and enrichment.
Uses mocked API responses to avoid network calls during testing.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from src.data.loaders.nvd_fetcher import (
    NVDFetcher,
    fetch_cve,
    fetch_epss,
    enrich_cve,
    NVD_API_URL,
    EPSS_API_URL,
    CACHE_TTL_DAYS,
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

# Sample EPSS API response
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

    @pytest.fixture
    def temp_cache_dir(self, tmp_path):
        """Create temporary cache directory."""
        return tmp_path

    def test_init_creates_empty_caches(self, temp_cache_dir):
        """New fetcher should start with empty caches."""
        fetcher = NVDFetcher(
            nvd_cache_file=temp_cache_dir / "nvd.json",
            epss_cache_file=temp_cache_dir / "epss.json"
        )
        assert fetcher._nvd_cache == {}
        assert fetcher._epss_cache == {}

    def test_init_loads_existing_cache(self, temp_cache_dir):
        """Fetcher should load existing cache from disk."""
        # Create cache file
        cache_file = temp_cache_dir / "nvd.json"
        cache_data = {"CVE-2021-44228": {"id": "CVE-2021-44228", "cached_at": datetime.now().isoformat()}}
        with open(cache_file, "w") as f:
            json.dump(cache_data, f)

        fetcher = NVDFetcher(
            nvd_cache_file=cache_file,
            epss_cache_file=temp_cache_dir / "epss.json"
        )
        assert "CVE-2021-44228" in fetcher._nvd_cache


class TestCacheValidation:
    """Tests for cache TTL validation."""

    @pytest.fixture
    def fetcher(self, tmp_path):
        """Create a fetcher with temp cache."""
        return NVDFetcher(
            nvd_cache_file=tmp_path / "nvd.json",
            epss_cache_file=tmp_path / "epss.json"
        )

    def test_valid_cache_entry(self, fetcher):
        """Recent cache entry should be valid."""
        entry = {"cached_at": datetime.now().isoformat()}
        assert fetcher._is_cache_valid(entry) is True

    def test_expired_cache_entry(self, fetcher):
        """Old cache entry should be invalid."""
        old_date = datetime.now() - timedelta(days=CACHE_TTL_DAYS + 1)
        entry = {"cached_at": old_date.isoformat()}
        assert fetcher._is_cache_valid(entry) is False

    def test_missing_cached_at(self, fetcher):
        """Entry without cached_at should be invalid."""
        entry = {"id": "CVE-2021-44228"}
        assert fetcher._is_cache_valid(entry) is False


class TestParseCVEItem:
    """Tests for parsing NVD CVE items."""

    @pytest.fixture
    def fetcher(self, tmp_path):
        """Create a fetcher with temp cache."""
        return NVDFetcher(
            nvd_cache_file=tmp_path / "nvd.json",
            epss_cache_file=tmp_path / "epss.json"
        )

    def test_parse_cve_id(self, fetcher):
        """Should extract CVE ID."""
        cve_item = SAMPLE_NVD_RESPONSE["vulnerabilities"][0]["cve"]
        result = fetcher._parse_cve_item(cve_item)
        assert result["id"] == "CVE-2021-44228"

    def test_parse_description(self, fetcher):
        """Should extract English description."""
        cve_item = SAMPLE_NVD_RESPONSE["vulnerabilities"][0]["cve"]
        result = fetcher._parse_cve_item(cve_item)
        assert "Log4j" in result["description"]
        assert "JNDI" in result["description"]

    def test_parse_cvss_v31(self, fetcher):
        """Should extract CVSS v3.1 metrics."""
        cve_item = SAMPLE_NVD_RESPONSE["vulnerabilities"][0]["cve"]
        result = fetcher._parse_cve_item(cve_item)
        assert result["cvss_vector"] == "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
        assert result["cvss_score"] == 10.0
        assert result["severity"] == "CRITICAL"

    def test_parse_cwe_ids(self, fetcher):
        """Should extract CWE IDs."""
        cve_item = SAMPLE_NVD_RESPONSE["vulnerabilities"][0]["cve"]
        result = fetcher._parse_cve_item(cve_item)
        assert "CWE-502" in result["cwe_ids"]
        assert "CWE-400" in result["cwe_ids"]

    def test_parse_dates(self, fetcher):
        """Should extract published and modified dates."""
        cve_item = SAMPLE_NVD_RESPONSE["vulnerabilities"][0]["cve"]
        result = fetcher._parse_cve_item(cve_item)
        assert "2021-12-10" in result["published"]
        assert result["modified"] != ""

    def test_parse_cvss_v30_fallback(self, fetcher):
        """Should fall back to CVSS v3.0 if v3.1 not available."""
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
    def fetcher(self, tmp_path):
        """Create a fetcher with temp cache."""
        return NVDFetcher(
            nvd_cache_file=tmp_path / "nvd.json",
            epss_cache_file=tmp_path / "epss.json"
        )

    def test_fetch_cve_uses_cache(self, fetcher):
        """Should return cached data without network request."""
        # Pre-populate cache
        fetcher._nvd_cache["CVE-2021-44228"] = {
            "id": "CVE-2021-44228",
            "description": "Cached description",
            "cached_at": datetime.now().isoformat(),
        }

        result = fetcher.fetch_cve("CVE-2021-44228", fetch_epss=False)
        assert result["description"] == "Cached description"

    @patch("src.data.loaders.nvd_fetcher.urlopen")
    def test_fetch_cve_from_api(self, mock_urlopen, fetcher):
        """Should fetch from NVD API when not in cache."""
        # Mock the API response
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
    def test_fetch_cve_caches_result(self, mock_urlopen, fetcher):
        """Should cache fetched CVE data."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(SAMPLE_NVD_RESPONSE).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        fetcher.fetch_cve("CVE-2021-44228", use_cache=False, fetch_epss=False)

        assert "CVE-2021-44228" in fetcher._nvd_cache


class TestFetchEPSS:
    """Tests for fetching EPSS scores."""

    @pytest.fixture
    def fetcher(self, tmp_path):
        """Create a fetcher with temp cache."""
        return NVDFetcher(
            nvd_cache_file=tmp_path / "nvd.json",
            epss_cache_file=tmp_path / "epss.json"
        )

    def test_fetch_epss_uses_cache(self, fetcher):
        """Should return cached EPSS score."""
        fetcher._epss_cache["CVE-2021-44228"] = {
            "epss_score": 0.975,
            "cached_at": datetime.now().isoformat(),
        }

        result = fetcher.fetch_epss("CVE-2021-44228")
        assert result == 0.975

    @patch("src.data.loaders.nvd_fetcher.urlopen")
    def test_fetch_epss_from_api(self, mock_urlopen, fetcher):
        """Should fetch from FIRST API when not in cache."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(SAMPLE_EPSS_RESPONSE).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = fetcher.fetch_epss("CVE-2021-44228", use_cache=False)

        assert result is not None
        assert result > 0.9  # Log4Shell has very high EPSS

    @patch("src.data.loaders.nvd_fetcher.urlopen")
    def test_fetch_epss_caches_result(self, mock_urlopen, fetcher):
        """Should cache fetched EPSS score."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(SAMPLE_EPSS_RESPONSE).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        fetcher.fetch_epss("CVE-2021-44228", use_cache=False)

        assert "CVE-2021-44228" in fetcher._epss_cache


class TestEnrichCVE:
    """Tests for CVE data enrichment."""

    @pytest.fixture
    def fetcher(self, tmp_path):
        """Create a fetcher with temp cache."""
        return NVDFetcher(
            nvd_cache_file=tmp_path / "nvd.json",
            epss_cache_file=tmp_path / "epss.json"
        )

    def test_enrich_fills_missing_description(self, fetcher):
        """Should fill in missing description from NVD."""
        # Pre-populate NVD cache
        fetcher._nvd_cache["CVE-2021-44228"] = {
            "id": "CVE-2021-44228",
            "description": "NVD description",
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
            "severity": "CRITICAL",
            "cwe_ids": ["CWE-502"],
            "cached_at": datetime.now().isoformat(),
        }

        cve_data = {"id": "CVE-2021-44228"}
        enriched = fetcher.enrich_cve_data(cve_data, fetch_if_missing=False)

        assert enriched["description"] == "NVD description"

    def test_enrich_fills_missing_cvss(self, fetcher):
        """Should fill in missing CVSS vector from NVD."""
        fetcher._nvd_cache["CVE-2021-44228"] = {
            "id": "CVE-2021-44228",
            "description": "Test",
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
            "cached_at": datetime.now().isoformat(),
        }

        cve_data = {"id": "CVE-2021-44228", "description": "Existing desc"}
        enriched = fetcher.enrich_cve_data(cve_data, fetch_if_missing=False)

        assert enriched["cvss_vector"] == "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
        # Should not overwrite existing description
        assert enriched["description"] == "Existing desc"

    def test_enrich_preserves_existing_data(self, fetcher):
        """Should not overwrite existing CVE data."""
        fetcher._nvd_cache["CVE-2021-44228"] = {
            "id": "CVE-2021-44228",
            "description": "NVD description",
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
            "cached_at": datetime.now().isoformat(),
        }

        cve_data = {
            "id": "CVE-2021-44228",
            "description": "My description",
            "cvss_vector": "CVSS:3.1/AV:L/AC:H/PR:H/UI:R/S:U/C:L/I:L/A:L",
        }
        enriched = fetcher.enrich_cve_data(cve_data, fetch_if_missing=False)

        # Should preserve existing values
        assert enriched["description"] == "My description"
        assert enriched["cvss_vector"] == "CVSS:3.1/AV:L/AC:H/PR:H/UI:R/S:U/C:L/I:L/A:L"


class TestBatchFetchEPSS:
    """Tests for batch EPSS fetching."""

    @pytest.fixture
    def fetcher(self, tmp_path):
        """Create a fetcher with temp cache."""
        return NVDFetcher(
            nvd_cache_file=tmp_path / "nvd.json",
            epss_cache_file=tmp_path / "epss.json"
        )

    @patch("src.data.loaders.nvd_fetcher.urlopen")
    def test_batch_fetch_multiple_cves(self, mock_urlopen, fetcher):
        """Should fetch EPSS for multiple CVEs in one request."""
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

        assert "CVE-2021-44228" in fetcher._epss_cache
        assert "CVE-2021-45046" in fetcher._epss_cache


class TestClearCache:
    """Tests for cache clearing."""

    def test_clear_cache(self, tmp_path):
        """Should clear all cached data."""
        nvd_file = tmp_path / "nvd.json"
        epss_file = tmp_path / "epss.json"

        fetcher = NVDFetcher(nvd_cache_file=nvd_file, epss_cache_file=epss_file)

        # Add some data
        fetcher._nvd_cache["CVE-TEST"] = {"id": "CVE-TEST"}
        fetcher._epss_cache["CVE-TEST"] = {"epss_score": 0.5}
        fetcher._save_nvd_cache()
        fetcher._save_epss_cache()

        # Clear cache
        fetcher.clear_cache()

        assert fetcher._nvd_cache == {}
        assert fetcher._epss_cache == {}
        assert not nvd_file.exists()
        assert not epss_file.exists()


class TestCacheStats:
    """Tests for cache statistics."""

    def test_get_cache_stats(self, tmp_path):
        """Should return correct cache statistics."""
        fetcher = NVDFetcher(
            nvd_cache_file=tmp_path / "nvd.json",
            epss_cache_file=tmp_path / "epss.json"
        )

        fetcher._nvd_cache = {"CVE-1": {}, "CVE-2": {}}
        fetcher._epss_cache = {"CVE-1": {}}

        stats = fetcher.get_cache_stats()

        assert stats["nvd_entries"] == 2
        assert stats["epss_entries"] == 1


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_fetch_cve_function_exists(self):
        """fetch_cve function should be importable."""
        from src.data.loaders.nvd_fetcher import fetch_cve
        assert callable(fetch_cve)

    def test_fetch_epss_function_exists(self):
        """fetch_epss function should be importable."""
        from src.data.loaders.nvd_fetcher import fetch_epss
        assert callable(fetch_epss)

    def test_enrich_cve_function_exists(self):
        """enrich_cve function should be importable."""
        from src.data.loaders.nvd_fetcher import enrich_cve
        assert callable(enrich_cve)
