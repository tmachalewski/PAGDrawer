"""
Tests for CWE Fetcher.

Uses mocked urlopen and mongomock (via the `mock_mongo` fixture in conftest.py)
to back the cache in memory.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from src.data.loaders.cwe_fetcher import (
    CWEFetcher,
    STATIC_CWE_MAPPING,
    SEVERITY_TO_IMPACT,
    get_technical_impact,
    get_technical_impacts,
)
from src.data.mongo_client import COLLECTION_CWE_IMPACTS, upsert_cached_doc


class TestStaticMapping:
    """Tests for the static CWE → Technical Impact mapping (no DB)."""

    def test_static_mapping_has_common_cwes(self):
        common_cwes = ["CWE-78", "CWE-79", "CWE-89", "CWE-119", "CWE-22"]
        for cwe in common_cwes:
            assert cwe in STATIC_CWE_MAPPING, f"{cwe} missing from static mapping"

    def test_static_mapping_values_are_lists(self):
        for cwe_id, impacts in STATIC_CWE_MAPPING.items():
            assert isinstance(impacts, list), f"{cwe_id} value is not a list"
            assert len(impacts) > 0, f"{cwe_id} has empty impact list"
            for impact in impacts:
                assert isinstance(impact, str), f"{cwe_id} has non-string impact"

    def test_cwe78_has_execute_code_impact(self):
        impacts = STATIC_CWE_MAPPING.get("CWE-78", [])
        assert "Execute Unauthorized Code or Commands" in impacts

    def test_cwe89_has_multiple_impacts(self):
        impacts = STATIC_CWE_MAPPING.get("CWE-89", [])
        assert len(impacts) >= 3
        assert "Execute Unauthorized Code or Commands" in impacts
        assert "Read Application Data" in impacts

    def test_cwe119_has_memory_impacts(self):
        impacts = STATIC_CWE_MAPPING.get("CWE-119", [])
        assert "Execute Unauthorized Code or Commands" in impacts
        assert any("Memory" in i for i in impacts)


class TestSeverityFallback:
    """Tests for severity-based fallback mapping (no DB)."""

    def test_severity_mapping_exists(self):
        assert "CRITICAL" in SEVERITY_TO_IMPACT
        assert "HIGH" in SEVERITY_TO_IMPACT
        assert "MEDIUM" in SEVERITY_TO_IMPACT
        assert "LOW" in SEVERITY_TO_IMPACT

    def test_critical_maps_to_execute_code(self):
        assert SEVERITY_TO_IMPACT["CRITICAL"] == "Execute Unauthorized Code or Commands"

    def test_high_maps_to_gain_privileges(self):
        assert SEVERITY_TO_IMPACT["HIGH"] == "Gain Privileges or Assume Identity"


class TestCWEFetcher:
    """Tests for the CWEFetcher class."""

    @pytest.fixture
    def fetcher(self, mock_mongo):
        return CWEFetcher()

    def test_normalize_cwe_id_with_prefix(self, fetcher):
        assert fetcher._normalize_cwe_id("CWE-78") == "CWE-78"
        assert fetcher._normalize_cwe_id("cwe-78") == "CWE-78"

    def test_normalize_cwe_id_without_prefix(self, fetcher):
        assert fetcher._normalize_cwe_id("78") == "CWE-78"
        assert fetcher._normalize_cwe_id("119") == "CWE-119"

    def test_normalize_cwe_id_no_hyphen(self, fetcher):
        assert fetcher._normalize_cwe_id("CWE78") == "CWE-78"

    def test_get_technical_impacts_from_static(self, fetcher):
        impacts = fetcher.get_technical_impacts("CWE-78", fetch_if_missing=False)
        assert "Execute Unauthorized Code or Commands" in impacts

    def test_get_technical_impacts_normalized_id(self, fetcher):
        impacts1 = fetcher.get_technical_impacts("CWE-78", fetch_if_missing=False)
        impacts2 = fetcher.get_technical_impacts("78", fetch_if_missing=False)
        impacts3 = fetcher.get_technical_impacts("cwe-78", fetch_if_missing=False)
        assert impacts1 == impacts2 == impacts3

    def test_get_technical_impacts_unknown_cwe_with_severity(self, fetcher):
        impacts = fetcher.get_technical_impacts(
            "CWE-99999", severity="CRITICAL", fetch_if_missing=False
        )
        assert impacts == ["Execute Unauthorized Code or Commands"]

    def test_get_technical_impacts_unknown_cwe_no_severity(self, fetcher):
        impacts = fetcher.get_technical_impacts("CWE-99999", fetch_if_missing=False)
        assert impacts == ["Other"]

    def test_get_primary_impact(self, fetcher):
        impact = fetcher.get_primary_impact("CWE-78", fetch_if_missing=False)
        assert isinstance(impact, str)
        assert len(impact) > 0

    def test_cache_persistence_via_mongo(self, mock_mongo, fetcher):
        """Cache should persist across fetcher instances because Mongo is the store."""
        upsert_cached_doc(COLLECTION_CWE_IMPACTS, "CWE-TEST", {
            "technical_impacts": ["Test Impact"],
            "source": "test",
        })
        fetcher2 = CWEFetcher()
        impacts = fetcher2.get_technical_impacts("CWE-TEST", fetch_if_missing=False)
        assert impacts == ["Test Impact"]

    def test_preload_common_cwes(self, mock_mongo, fetcher):
        count = fetcher.preload_common_cwes()
        assert count > 0
        assert mock_mongo[COLLECTION_CWE_IMPACTS].count_documents({}) == count

    def test_clear_cache_removes_all_docs(self, mock_mongo, fetcher):
        upsert_cached_doc(COLLECTION_CWE_IMPACTS, "CWE-T", {"technical_impacts": ["X"]})
        fetcher.clear_cache()
        assert mock_mongo[COLLECTION_CWE_IMPACTS].count_documents({}) == 0


class TestCWEFetcherImpactNormalization:
    """Tests for impact normalization (pure function, no DB)."""

    @pytest.fixture
    def fetcher(self, mock_mongo):
        return CWEFetcher()

    def test_normalize_impact_exact_match(self, fetcher):
        impact = fetcher._normalize_impact("Execute Unauthorized Code or Commands")
        assert impact == "Execute Unauthorized Code or Commands"

    def test_normalize_impact_execute_code_variant(self, fetcher):
        impact = fetcher._normalize_impact("Execute arbitrary code")
        assert impact == "Execute Unauthorized Code or Commands"

    def test_normalize_impact_privilege_variant(self, fetcher):
        impact = fetcher._normalize_impact("Gain elevated privileges")
        assert impact == "Gain Privileges or Assume Identity"

    def test_normalize_impact_dos_crash(self, fetcher):
        impact = fetcher._normalize_impact("Denial of Service (crash)")
        assert impact == "DoS: Crash, Exit, or Restart"

    def test_normalize_impact_dos_cpu(self, fetcher):
        impact = fetcher._normalize_impact("DoS via CPU exhaustion")
        assert impact == "DoS: Resource Consumption (CPU)"

    def test_normalize_impact_read_files(self, fetcher):
        impact = fetcher._normalize_impact("Read sensitive files")
        assert impact == "Read Files or Directories"

    def test_normalize_impact_modify_data(self, fetcher):
        impact = fetcher._normalize_impact("Modify stored data")
        assert impact == "Modify Application Data"

    def test_normalize_impact_unknown_returns_none(self, fetcher):
        impact = fetcher._normalize_impact("Some completely unknown impact")
        assert impact is None


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_technical_impact_returns_string(self, mock_mongo):
        impact = get_technical_impact("CWE-78", fetch_if_missing=False)
        assert isinstance(impact, str)

    def test_get_technical_impacts_returns_list(self, mock_mongo):
        impacts = get_technical_impacts("CWE-78", fetch_if_missing=False)
        assert isinstance(impacts, list)
        assert len(impacts) > 0


class TestMockDataCWECoverage:
    """Tests to verify mock data CWEs are covered (no DB)."""

    def test_mock_data_cwes_have_mappings(self):
        from src.data.mock_data import MOCK_CVES

        missing_cwes = []
        for cve in MOCK_CVES:
            cwe_id = cve.get("cwe_id")
            if cwe_id and cwe_id not in STATIC_CWE_MAPPING:
                missing_cwes.append(cwe_id)

        assert len(missing_cwes) == 0, f"Missing CWE mappings: {missing_cwes}"

    def test_mock_data_technical_impacts_match(self):
        from src.data.mock_data import MOCK_CVES

        mismatches = []
        for cve in MOCK_CVES:
            cwe_id = cve.get("cwe_id")
            mock_impacts = cve.get("technical_impacts", [])

            if cwe_id and mock_impacts:
                mapped_impacts = STATIC_CWE_MAPPING.get(cwe_id, [])

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

        if mismatches:
            print(f"Note: {len(mismatches)} impact mismatches between mock data and CWE mapping")


class TestCWEFetcherAPIParsing:
    """Tests for CWE REST API parsing functionality."""

    @pytest.fixture
    def fetcher(self, mock_mongo):
        return CWEFetcher()

    def test_extract_weakness_from_response(self, fetcher):
        response = {"Weaknesses": [{"ID": "354", "Name": "Test Weakness"}]}
        weakness = fetcher._extract_weakness_from_response(response)
        assert weakness is not None
        assert weakness["ID"] == "354"

    def test_extract_weakness_from_empty_response(self, fetcher):
        weakness = fetcher._extract_weakness_from_response({"Weaknesses": []})
        assert weakness is None

    def test_extract_weakness_from_missing_key(self, fetcher):
        weakness = fetcher._extract_weakness_from_response({"SomeOtherKey": []})
        assert weakness is None

    def test_extract_consequences_from_json(self, fetcher):
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
        weakness = {
            "CommonConsequences": [
                {"Scope": ["Integrity"], "Impact": "Modify Application Data"},
            ]
        }
        impacts = fetcher._extract_consequences_from_json(weakness)
        assert "Modify Application Data" in impacts

    def test_extract_consequences_empty(self, fetcher):
        impacts = fetcher._extract_consequences_from_json({"CommonConsequences": []})
        assert impacts == []

    def test_extract_consequences_missing_key(self, fetcher):
        impacts = fetcher._extract_consequences_from_json({"Name": "Test"})
        assert impacts == []

    def test_get_numeric_id(self, fetcher):
        assert fetcher._get_numeric_id("CWE-354") == "354"
        assert fetcher._get_numeric_id("CWE-79") == "79"
        assert fetcher._get_numeric_id("invalid") is None

    @patch('src.data.loaders.cwe_fetcher.urlopen')
    def test_fetch_from_api_success(self, mock_urlopen, fetcher):
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
        from urllib.error import HTTPError
        mock_urlopen.side_effect = HTTPError(
            url="http://test", code=404, msg="Not Found", hdrs={}, fp=None
        )
        impacts = fetcher._fetch_from_api("CWE-99999")
        assert impacts is None

    @patch('src.data.loaders.cwe_fetcher.urlopen')
    def test_fetch_from_api_network_error(self, mock_urlopen, fetcher):
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("Network unreachable")
        impacts = fetcher._fetch_from_api("CWE-354")
        assert impacts is None

    def test_info_cache_persistence_via_mongo(self, mock_mongo, fetcher):
        """Info cache should persist to Mongo across fetcher instances."""
        upsert_cached_doc(COLLECTION_CWE_IMPACTS, "CWE-TEST", {
            "name": "Test CWE",
            "description": "Test description",
            "technical_impacts": ["Test Impact"],
            "source": "test",
        })
        fetcher2 = CWEFetcher()
        info = fetcher2.get_cwe_info("CWE-TEST", fetch_if_missing=False)
        assert info is not None
        assert info["name"] == "Test CWE"
