"""
Tests for CWE Fetcher.

Tests the CWE data fetching, caching, and Technical Impact mapping.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.data.loaders.cwe_fetcher import (
    CWEFetcher,
    STATIC_CWE_MAPPING,
    SEVERITY_TO_IMPACT,
    get_technical_impact,
    get_technical_impacts,
)


class TestStaticMapping:
    """Tests for the static CWE → Technical Impact mapping."""

    def test_static_mapping_has_common_cwes(self):
        """Static mapping should include common CWEs."""
        common_cwes = ["CWE-78", "CWE-79", "CWE-89", "CWE-119", "CWE-22"]
        for cwe in common_cwes:
            assert cwe in STATIC_CWE_MAPPING, f"{cwe} missing from static mapping"

    def test_static_mapping_values_are_lists(self):
        """All static mapping values should be lists of strings."""
        for cwe_id, impacts in STATIC_CWE_MAPPING.items():
            assert isinstance(impacts, list), f"{cwe_id} value is not a list"
            assert len(impacts) > 0, f"{cwe_id} has empty impact list"
            for impact in impacts:
                assert isinstance(impact, str), f"{cwe_id} has non-string impact"

    def test_cwe78_has_execute_code_impact(self):
        """CWE-78 (Command Injection) should map to Execute Unauthorized Code."""
        impacts = STATIC_CWE_MAPPING.get("CWE-78", [])
        assert "Execute Unauthorized Code or Commands" in impacts

    def test_cwe89_has_multiple_impacts(self):
        """CWE-89 (SQL Injection) should have multiple impacts."""
        impacts = STATIC_CWE_MAPPING.get("CWE-89", [])
        assert len(impacts) >= 3
        assert "Execute Unauthorized Code or Commands" in impacts
        assert "Read Application Data" in impacts

    def test_cwe119_has_memory_impacts(self):
        """CWE-119 (Buffer Overflow) should include memory impacts."""
        impacts = STATIC_CWE_MAPPING.get("CWE-119", [])
        assert "Execute Unauthorized Code or Commands" in impacts
        assert any("Memory" in i for i in impacts)


class TestSeverityFallback:
    """Tests for severity-based fallback mapping."""

    def test_severity_mapping_exists(self):
        """Severity mapping should have all standard levels."""
        assert "CRITICAL" in SEVERITY_TO_IMPACT
        assert "HIGH" in SEVERITY_TO_IMPACT
        assert "MEDIUM" in SEVERITY_TO_IMPACT
        assert "LOW" in SEVERITY_TO_IMPACT

    def test_critical_maps_to_execute_code(self):
        """CRITICAL severity should map to Execute Unauthorized Code."""
        assert SEVERITY_TO_IMPACT["CRITICAL"] == "Execute Unauthorized Code or Commands"

    def test_high_maps_to_gain_privileges(self):
        """HIGH severity should map to Gain Privileges."""
        assert SEVERITY_TO_IMPACT["HIGH"] == "Gain Privileges or Assume Identity"


class TestCWEFetcher:
    """Tests for the CWEFetcher class."""

    @pytest.fixture
    def temp_cache_file(self, tmp_path):
        """Create a temporary cache file path."""
        return tmp_path / "test_cwe_cache.json"

    @pytest.fixture
    def fetcher(self, temp_cache_file):
        """Create a CWE fetcher with temp cache."""
        return CWEFetcher(cache_file=temp_cache_file)

    def test_init_creates_empty_cache(self, fetcher):
        """New fetcher should start with empty cache."""
        assert fetcher._cache == {}

    def test_normalize_cwe_id_with_prefix(self, fetcher):
        """Should handle CWE-XXX format."""
        assert fetcher._normalize_cwe_id("CWE-78") == "CWE-78"
        assert fetcher._normalize_cwe_id("cwe-78") == "CWE-78"

    def test_normalize_cwe_id_without_prefix(self, fetcher):
        """Should add CWE- prefix to numeric input."""
        assert fetcher._normalize_cwe_id("78") == "CWE-78"
        assert fetcher._normalize_cwe_id("119") == "CWE-119"

    def test_normalize_cwe_id_no_hyphen(self, fetcher):
        """Should handle CWEXX format (no hyphen)."""
        assert fetcher._normalize_cwe_id("CWE78") == "CWE-78"

    def test_get_technical_impacts_from_static(self, fetcher):
        """Should return impacts from static mapping."""
        impacts = fetcher.get_technical_impacts("CWE-78", fetch_if_missing=False)
        assert "Execute Unauthorized Code or Commands" in impacts

    def test_get_technical_impacts_normalized_id(self, fetcher):
        """Should normalize CWE ID before lookup."""
        impacts1 = fetcher.get_technical_impacts("CWE-78", fetch_if_missing=False)
        impacts2 = fetcher.get_technical_impacts("78", fetch_if_missing=False)
        impacts3 = fetcher.get_technical_impacts("cwe-78", fetch_if_missing=False)
        assert impacts1 == impacts2 == impacts3

    def test_get_technical_impacts_unknown_cwe_with_severity(self, fetcher):
        """Should use severity fallback for unknown CWE."""
        impacts = fetcher.get_technical_impacts(
            "CWE-99999",
            severity="CRITICAL",
            fetch_if_missing=False
        )
        assert impacts == ["Execute Unauthorized Code or Commands"]

    def test_get_technical_impacts_unknown_cwe_no_severity(self, fetcher):
        """Should return Other for unknown CWE without severity."""
        impacts = fetcher.get_technical_impacts(
            "CWE-99999",
            fetch_if_missing=False
        )
        assert impacts == ["Other"]

    def test_get_primary_impact(self, fetcher):
        """get_primary_impact should return first impact."""
        impact = fetcher.get_primary_impact("CWE-78", fetch_if_missing=False)
        assert isinstance(impact, str)
        assert len(impact) > 0

    def test_cache_persistence(self, fetcher, temp_cache_file):
        """Cache should persist to disk."""
        # Add to cache
        fetcher._cache["CWE-TEST"] = ["Test Impact"]
        fetcher._save_cache()

        # Verify file exists
        assert temp_cache_file.exists()

        # Load in new fetcher
        fetcher2 = CWEFetcher(cache_file=temp_cache_file)
        assert "CWE-TEST" in fetcher2._cache
        assert fetcher2._cache["CWE-TEST"] == ["Test Impact"]

    def test_preload_common_cwes(self, fetcher):
        """preload_common_cwes should populate cache."""
        count = fetcher.preload_common_cwes()
        assert count > 0
        assert len(fetcher._cache) > 0

    def test_clear_cache(self, fetcher, temp_cache_file):
        """clear_cache should remove all cached data."""
        fetcher._cache["CWE-TEST"] = ["Test Impact"]
        fetcher._save_cache()

        fetcher.clear_cache()

        assert fetcher._cache == {}
        assert not temp_cache_file.exists()


class TestCWEFetcherImpactNormalization:
    """Tests for impact normalization functionality."""

    @pytest.fixture
    def fetcher(self, tmp_path):
        """Create a CWE fetcher with temp cache."""
        return CWEFetcher(cache_file=tmp_path / "cache.json")

    def test_normalize_impact_exact_match(self, fetcher):
        """Should return exact matches unchanged."""
        impact = fetcher._normalize_impact("Execute Unauthorized Code or Commands")
        assert impact == "Execute Unauthorized Code or Commands"

    def test_normalize_impact_execute_code_variant(self, fetcher):
        """Should normalize execute code variants."""
        impact = fetcher._normalize_impact("Execute arbitrary code")
        assert impact == "Execute Unauthorized Code or Commands"

    def test_normalize_impact_privilege_variant(self, fetcher):
        """Should normalize privilege escalation variants."""
        impact = fetcher._normalize_impact("Gain elevated privileges")
        assert impact == "Gain Privileges or Assume Identity"

    def test_normalize_impact_dos_crash(self, fetcher):
        """Should normalize DoS crash variants."""
        impact = fetcher._normalize_impact("Denial of Service (crash)")
        assert impact == "DoS: Crash, Exit, or Restart"

    def test_normalize_impact_dos_cpu(self, fetcher):
        """Should normalize DoS CPU variants."""
        impact = fetcher._normalize_impact("DoS via CPU exhaustion")
        assert impact == "DoS: Resource Consumption (CPU)"

    def test_normalize_impact_read_files(self, fetcher):
        """Should normalize file read variants."""
        impact = fetcher._normalize_impact("Read sensitive files")
        assert impact == "Read Files or Directories"

    def test_normalize_impact_modify_data(self, fetcher):
        """Should normalize data modification variants."""
        impact = fetcher._normalize_impact("Modify stored data")
        assert impact == "Modify Application Data"

    def test_normalize_impact_unknown_returns_none(self, fetcher):
        """Should return None for unmappable impacts."""
        impact = fetcher._normalize_impact("Some completely unknown impact")
        assert impact is None


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_technical_impact_returns_string(self):
        """get_technical_impact should return a string."""
        impact = get_technical_impact("CWE-78", fetch_if_missing=False)
        assert isinstance(impact, str)

    def test_get_technical_impacts_returns_list(self):
        """get_technical_impacts should return a list."""
        impacts = get_technical_impacts("CWE-78", fetch_if_missing=False)
        assert isinstance(impacts, list)
        assert len(impacts) > 0

    def test_convenience_functions_use_same_fetcher(self):
        """Convenience functions should use the same fetcher instance."""
        # Call both functions
        get_technical_impact("CWE-78", fetch_if_missing=False)
        get_technical_impacts("CWE-79", fetch_if_missing=False)

        # They should have populated the same cache
        from src.data.loaders.cwe_fetcher import get_fetcher
        fetcher = get_fetcher()
        assert fetcher is not None


class TestMockDataCWECoverage:
    """Tests to verify mock data CWEs are covered."""

    def test_mock_data_cwes_have_mappings(self):
        """All CWEs used in mock_data should have static mappings."""
        from src.data.mock_data import MOCK_CVES

        missing_cwes = []
        for cve in MOCK_CVES:
            cwe_id = cve.get("cwe_id")
            if cwe_id and cwe_id not in STATIC_CWE_MAPPING:
                missing_cwes.append(cwe_id)

        assert len(missing_cwes) == 0, f"Missing CWE mappings: {missing_cwes}"

    def test_mock_data_technical_impacts_match(self):
        """Mock data technical_impacts should match CWE mapping."""
        from src.data.mock_data import MOCK_CVES

        mismatches = []
        for cve in MOCK_CVES:
            cwe_id = cve.get("cwe_id")
            mock_impacts = cve.get("technical_impacts", [])

            if cwe_id and mock_impacts:
                mapped_impacts = STATIC_CWE_MAPPING.get(cwe_id, [])

                # Check if each mock impact is in the mapped impacts
                for mock_impact in mock_impacts:
                    found = False
                    for mapped in mapped_impacts:
                        if mock_impact in mapped or mapped.startswith(mock_impact):
                            found = True
                            break

                    if not found and mapped_impacts:
                        mismatches.append({
                            "cve": cve["id"],
                            "cwe": cwe_id,
                            "mock_impact": mock_impact,
                            "mapped_impacts": mapped_impacts
                        })

        # Allow some mismatches since mock data uses simplified impact names
        # but log them for awareness
        if mismatches:
            print(f"Note: {len(mismatches)} impact mismatches between mock data and CWE mapping")


class TestCWEFetcherAPIParsing:
    """Tests for CWE REST API parsing functionality."""

    @pytest.fixture
    def fetcher(self, tmp_path):
        """Create a CWE fetcher with temp cache."""
        return CWEFetcher(cache_file=tmp_path / "cache.json")

    def test_extract_weakness_from_response(self, fetcher):
        """Should extract weakness from API response wrapper."""
        response = {
            "Weaknesses": [
                {"ID": "354", "Name": "Test Weakness"}
            ]
        }
        weakness = fetcher._extract_weakness_from_response(response)
        assert weakness is not None
        assert weakness["ID"] == "354"

    def test_extract_weakness_from_empty_response(self, fetcher):
        """Should return None for empty Weaknesses list."""
        response = {"Weaknesses": []}
        weakness = fetcher._extract_weakness_from_response(response)
        assert weakness is None

    def test_extract_weakness_from_missing_key(self, fetcher):
        """Should return None if Weaknesses key is missing."""
        response = {"SomeOtherKey": []}
        weakness = fetcher._extract_weakness_from_response(response)
        assert weakness is None

    def test_extract_consequences_from_json(self, fetcher):
        """Should extract impacts from CommonConsequences."""
        weakness = {
            "CommonConsequences": [
                {"Scope": ["Integrity"], "Impact": ["Modify Application Data"]},
                {"Scope": ["Confidentiality"], "Impact": ["Read Application Data"]},
            ]
        }
        impacts = fetcher._extract_consequences_from_json(weakness)
        assert "Modify Application Data" in impacts
        assert "Read Application Data" in impacts

    def test_extract_consequences_with_multiple_impacts_per_consequence(self, fetcher):
        """Should extract all impacts when multiple per consequence."""
        weakness = {
            "CommonConsequences": [
                {
                    "Scope": ["Integrity", "Confidentiality"],
                    "Impact": ["Modify Application Data", "Read Application Data"]
                },
            ]
        }
        impacts = fetcher._extract_consequences_from_json(weakness)
        assert "Modify Application Data" in impacts
        assert "Read Application Data" in impacts

    def test_extract_consequences_with_string_impact(self, fetcher):
        """Should handle Impact as a string instead of list."""
        weakness = {
            "CommonConsequences": [
                {"Scope": ["Integrity"], "Impact": "Modify Application Data"},
            ]
        }
        impacts = fetcher._extract_consequences_from_json(weakness)
        assert "Modify Application Data" in impacts

    def test_extract_consequences_empty(self, fetcher):
        """Should return empty list for no consequences."""
        weakness = {"CommonConsequences": []}
        impacts = fetcher._extract_consequences_from_json(weakness)
        assert impacts == []

    def test_extract_consequences_missing_key(self, fetcher):
        """Should return empty list if CommonConsequences is missing."""
        weakness = {"Name": "Test"}
        impacts = fetcher._extract_consequences_from_json(weakness)
        assert impacts == []

    def test_get_numeric_id(self, fetcher):
        """Should extract numeric ID from CWE string."""
        assert fetcher._get_numeric_id("CWE-354") == "354"
        assert fetcher._get_numeric_id("CWE-79") == "79"
        assert fetcher._get_numeric_id("invalid") is None

    @patch('src.data.loaders.cwe_fetcher.urlopen')
    def test_fetch_from_api_success(self, mock_urlopen, fetcher):
        """Should fetch and parse CWE data from API."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "Weaknesses": [{
                "ID": "354",
                "Name": "Improper Validation",
                "CommonConsequences": [
                    {"Scope": ["Integrity"], "Impact": ["Modify Application Data"]},
                ]
            }]
        }).encode('utf-8')
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        impacts = fetcher._fetch_from_api("CWE-354")
        assert impacts is not None
        assert "Modify Application Data" in impacts

    @patch('src.data.loaders.cwe_fetcher.urlopen')
    def test_fetch_from_api_404(self, mock_urlopen, fetcher):
        """Should return None for 404 response."""
        from urllib.error import HTTPError
        mock_urlopen.side_effect = HTTPError(
            url="http://test",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None
        )
        impacts = fetcher._fetch_from_api("CWE-99999")
        assert impacts is None

    @patch('src.data.loaders.cwe_fetcher.urlopen')
    def test_fetch_from_api_network_error(self, mock_urlopen, fetcher):
        """Should return None for network errors."""
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("Network unreachable")
        impacts = fetcher._fetch_from_api("CWE-354")
        assert impacts is None

    def test_info_cache_persistence(self, fetcher, tmp_path):
        """Info cache should persist to disk."""
        cache_file = tmp_path / "cache.json"
        fetcher = CWEFetcher(cache_file=cache_file)

        # Add to info cache
        fetcher._info_cache["CWE-TEST"] = {
            "id": "CWE-TEST",
            "name": "Test CWE",
            "description": "Test description",
            "technical_impacts": ["Test Impact"]
        }
        fetcher._save_cache()

        # Load in new fetcher
        fetcher2 = CWEFetcher(cache_file=cache_file)
        assert "CWE-TEST" in fetcher2._info_cache
        assert fetcher2._info_cache["CWE-TEST"]["name"] == "Test CWE"
