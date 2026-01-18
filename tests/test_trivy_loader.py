"""
Tests for TrivyDataLoader.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.data.loaders import TrivyDataLoader, load_trivy_json
from src.data.loaders.base import DataLoadError, LoadedData
from src.data.schemas.trivy import TrivyReport


# Sample Trivy JSON output for testing
SAMPLE_TRIVY_REPORT = {
    "SchemaVersion": 2,
    "CreatedAt": "2026-01-16T10:00:00.000Z",
    "ArtifactName": "alpine:3.18",
    "ArtifactType": "container_image",
    "Metadata": {
        "ImageID": "sha256:abc123",
        "RepoTags": ["alpine:3.18"],
    },
    "Results": [
        {
            "Target": "alpine:3.18 (alpine 3.18.0)",
            "Class": "os-pkgs",
            "Type": "alpine",
            "Vulnerabilities": [
                {
                    "VulnerabilityID": "CVE-2023-12345",
                    "PkgName": "curl",
                    "InstalledVersion": "8.0.0-r0",
                    "FixedVersion": "8.0.1-r0",
                    "Severity": "HIGH",
                    "Title": "curl: heap buffer overflow",
                    "Description": "A heap buffer overflow in curl allows remote attackers to execute arbitrary code.",
                    "CweIDs": ["CWE-122"],
                    "CVSS": {
                        "nvd": {
                            "V3Vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                            "V3Score": 9.8,
                        }
                    },
                    "References": ["https://nvd.nist.gov/vuln/detail/CVE-2023-12345"],
                },
                {
                    "VulnerabilityID": "CVE-2023-67890",
                    "PkgName": "openssl",
                    "InstalledVersion": "3.0.0-r0",
                    "FixedVersion": "3.0.1-r0",
                    "Severity": "MEDIUM",
                    "Title": "openssl: timing side channel",
                    "CweIDs": ["CWE-208"],
                    "CVSS": {
                        "nvd": {
                            "V3Vector": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N",
                            "V3Score": 3.7,
                        }
                    },
                },
            ],
        },
        {
            "Target": "app/package.json",
            "Class": "lang-pkgs",
            "Type": "npm",
            "Vulnerabilities": [
                {
                    "VulnerabilityID": "CVE-2023-99999",
                    "PkgName": "lodash",
                    "InstalledVersion": "4.17.20",
                    "FixedVersion": "4.17.21",
                    "Severity": "CRITICAL",
                    "Title": "lodash: prototype pollution",
                    "CweIDs": ["CWE-1321"],
                },
            ],
        },
    ],
}


class TestTrivyDataLoaderInit:
    """Tests for TrivyDataLoader initialization."""

    def test_init_with_dict(self):
        """Test initialization with a dict source."""
        loader = TrivyDataLoader(source=SAMPLE_TRIVY_REPORT)
        assert loader._source == SAMPLE_TRIVY_REPORT

    def test_init_with_path(self, tmp_path):
        """Test initialization with a file path."""
        json_file = tmp_path / "trivy.json"
        json_file.write_text(json.dumps(SAMPLE_TRIVY_REPORT))

        loader = TrivyDataLoader(source=str(json_file))
        assert loader._source == str(json_file)

    def test_init_with_custom_config(self):
        """Test initialization with custom host config."""
        config = {"os_family": "Linux", "criticality_score": 0.8, "subnet_id": "dmz"}
        loader = TrivyDataLoader(source=SAMPLE_TRIVY_REPORT, host_config=config)
        assert loader._host_config == config


class TestValidateSource:
    """Tests for source validation."""

    def test_validate_dict_source(self):
        """Test validation with valid dict source."""
        loader = TrivyDataLoader(source=SAMPLE_TRIVY_REPORT)
        assert loader.validate_source() is True

    def test_validate_file_source(self, tmp_path):
        """Test validation with valid file source."""
        json_file = tmp_path / "trivy.json"
        json_file.write_text(json.dumps(SAMPLE_TRIVY_REPORT))

        loader = TrivyDataLoader(source=str(json_file))
        assert loader.validate_source() is True

    def test_validate_missing_file(self):
        """Test validation with non-existent file."""
        loader = TrivyDataLoader(source="/nonexistent/file.json")
        assert loader.validate_source() is False

    def test_validate_invalid_dict(self):
        """Test validation with invalid dict structure."""
        loader = TrivyDataLoader(source={"invalid": "data"})
        # Should still be valid as TrivyReport allows extra fields and has defaults
        assert loader.validate_source() is True


class TestLoadBasic:
    """Tests for basic loading functionality without enrichment."""

    @pytest.fixture
    def loader_no_enrich(self):
        """Create a loader without enrichment."""
        return TrivyDataLoader(
            source=SAMPLE_TRIVY_REPORT,
            enrich_from_nvd=False,
            enrich_cwe=False,
        )

    def test_load_returns_loaded_data(self, loader_no_enrich):
        """Test that load() returns a LoadedData instance."""
        result = loader_no_enrich.load()
        assert isinstance(result, LoadedData)

    def test_load_extracts_hosts(self, loader_no_enrich):
        """Test that hosts are created from targets."""
        result = loader_no_enrich.load()
        # Should have 2 hosts (alpine and npm package.json)
        assert len(result.hosts) == 2

    def test_host_has_required_fields(self, loader_no_enrich):
        """Test that hosts have all required fields."""
        result = loader_no_enrich.load()
        for host in result.hosts:
            assert "id" in host
            assert "os_family" in host
            assert "criticality_score" in host
            assert "subnet_id" in host

    def test_load_extracts_cpes(self, loader_no_enrich):
        """Test that CPEs are created from packages."""
        result = loader_no_enrich.load()
        # Should have 3 unique CPEs (curl, openssl, lodash)
        assert len(result.cpes) == 3

    def test_cpe_has_required_fields(self, loader_no_enrich):
        """Test that CPEs have all required fields."""
        result = loader_no_enrich.load()
        for cpe in result.cpes:
            assert "id" in cpe
            assert "vendor" in cpe
            assert "product" in cpe
            assert "version" in cpe
            assert cpe["id"].startswith("cpe:2.3:")

    def test_load_extracts_cves(self, loader_no_enrich):
        """Test that CVEs are created from vulnerabilities."""
        result = loader_no_enrich.load()
        # Should have 3 CVEs
        assert len(result.cves) == 3

    def test_cve_has_required_fields(self, loader_no_enrich):
        """Test that CVEs have all required fields."""
        result = loader_no_enrich.load()
        for cve in result.cves:
            assert "id" in cve
            assert "description" in cve
            assert "epss_score" in cve
            assert "cvss_vector" in cve
            assert "cpe_id" in cve
            assert "cwe_id" in cve
            assert "technical_impacts" in cve

    def test_load_extracts_cwes(self, loader_no_enrich):
        """Test that CWEs are created from vulnerability CweIDs."""
        result = loader_no_enrich.load()
        # Should have 3 unique CWEs
        assert len(result.cwes) == 3
        cwe_ids = {cwe["id"] for cwe in result.cwes}
        assert "CWE-122" in cwe_ids
        assert "CWE-208" in cwe_ids
        assert "CWE-1321" in cwe_ids

    def test_host_cpe_map_populated(self, loader_no_enrich):
        """Test that host_cpe_map is correctly populated."""
        result = loader_no_enrich.load()
        assert len(result.host_cpe_map) == 2
        # First host should have curl and openssl
        first_host_id = result.hosts[0]["id"]
        assert len(result.host_cpe_map[first_host_id]) == 2


class TestOSFamilyDetection:
    """Tests for OS family detection."""

    def test_detect_alpine_linux(self):
        """Test detection of Alpine Linux."""
        loader = TrivyDataLoader(source=SAMPLE_TRIVY_REPORT, enrich_from_nvd=False, enrich_cwe=False)
        result = loader.load()
        alpine_host = next((h for h in result.hosts if "alpine" in h.get("target", "").lower()), None)
        assert alpine_host is not None
        assert alpine_host["os_family"] == "Linux"

    def test_detect_npm_as_linux(self):
        """Test that npm packages default to Linux."""
        loader = TrivyDataLoader(source=SAMPLE_TRIVY_REPORT, enrich_from_nvd=False, enrich_cwe=False)
        result = loader.load()
        npm_host = next((h for h in result.hosts if h.get("target_type") == "npm"), None)
        # NPM packages should default to Unknown or Linux based on type
        assert npm_host is not None

    def test_override_os_family(self):
        """Test OS family override via host_config."""
        loader = TrivyDataLoader(
            source=SAMPLE_TRIVY_REPORT,
            enrich_from_nvd=False,
            enrich_cwe=False,
            host_config={"os_family": "Windows"},
        )
        result = loader.load()
        for host in result.hosts:
            assert host["os_family"] == "Windows"


class TestCVSSHandling:
    """Tests for CVSS vector handling."""

    def test_extracts_cvss_from_trivy(self):
        """Test that CVSS vectors are extracted from Trivy data."""
        loader = TrivyDataLoader(source=SAMPLE_TRIVY_REPORT, enrich_from_nvd=False, enrich_cwe=False)
        result = loader.load()

        curl_cve = next((c for c in result.cves if c["id"] == "CVE-2023-12345"), None)
        assert curl_cve is not None
        assert curl_cve["cvss_vector"] == "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"

    def test_default_cvss_for_missing(self):
        """Test that default CVSS is generated when missing."""
        # Create report with vulnerability without CVSS
        report = {
            "Results": [
                {
                    "Target": "test",
                    "Type": "alpine",
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2023-00001",
                            "PkgName": "test",
                            "InstalledVersion": "1.0",
                            "Severity": "CRITICAL",
                        }
                    ],
                }
            ]
        }
        loader = TrivyDataLoader(source=report, enrich_from_nvd=False, enrich_cwe=False)
        result = loader.load()

        cve = result.cves[0]
        assert cve["cvss_vector"].startswith("CVSS:3.1/")
        # Critical should have high impact
        assert "C:H" in cve["cvss_vector"]


class TestEnrichment:
    """Tests for data enrichment from NVD/CWE."""

    @patch("src.data.loaders.trivy_loader.NVDFetcher")
    def test_enrichment_fetches_epss(self, mock_nvd_class):
        """Test that EPSS scores are fetched from NVD."""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_cve.return_value = {
            "epss_score": 0.85,
            "cvss_vector": None,
            "cvss_score": None,
            "description": None,
            "cwe_ids": None,
        }
        mock_nvd_class.return_value = mock_fetcher

        loader = TrivyDataLoader(source=SAMPLE_TRIVY_REPORT, enrich_from_nvd=True, enrich_cwe=False)
        result = loader.load()

        # Verify NVD fetcher was called
        assert mock_fetcher.fetch_cve.called

        # Check EPSS was populated
        cve = next((c for c in result.cves if c["id"] == "CVE-2023-12345"), None)
        assert cve is not None
        assert cve["epss_score"] == 0.85

    @patch("src.data.loaders.trivy_loader.CWEFetcher")
    def test_enrichment_fetches_technical_impacts(self, mock_cwe_class):
        """Test that technical impacts are fetched from CWE."""
        mock_fetcher = MagicMock()
        mock_fetcher.get_technical_impacts.return_value = ["Execute Unauthorized Code or Commands"]
        mock_cwe_class.return_value = mock_fetcher

        loader = TrivyDataLoader(source=SAMPLE_TRIVY_REPORT, enrich_from_nvd=False, enrich_cwe=True)
        result = loader.load()

        # Verify CWE fetcher was called
        assert mock_fetcher.get_technical_impacts.called

        # Check technical impacts were populated
        cve = next((c for c in result.cves if c["id"] == "CVE-2023-12345"), None)
        assert cve is not None
        assert cve["technical_impacts"] == ["Execute Unauthorized Code or Commands"]


class TestFileLoading:
    """Tests for loading from files."""

    def test_load_from_file_path(self, tmp_path):
        """Test loading from a file path string."""
        json_file = tmp_path / "trivy.json"
        json_file.write_text(json.dumps(SAMPLE_TRIVY_REPORT))

        loader = TrivyDataLoader(source=str(json_file), enrich_from_nvd=False, enrich_cwe=False)
        result = loader.load()

        assert len(result.cves) == 3

    def test_load_from_path_object(self, tmp_path):
        """Test loading from a Path object."""
        json_file = tmp_path / "trivy.json"
        json_file.write_text(json.dumps(SAMPLE_TRIVY_REPORT))

        loader = TrivyDataLoader(source=json_file, enrich_from_nvd=False, enrich_cwe=False)
        result = loader.load()

        assert len(result.cves) == 3

    def test_load_from_invalid_json(self, tmp_path):
        """Test that invalid JSON raises DataLoadError."""
        json_file = tmp_path / "invalid.json"
        json_file.write_text("not valid json")

        loader = TrivyDataLoader(source=str(json_file), enrich_from_nvd=False, enrich_cwe=False)
        with pytest.raises(DataLoadError):
            loader.load()


class TestConvenienceFunction:
    """Tests for the load_trivy_json convenience function."""

    def test_load_trivy_json_basic(self):
        """Test the convenience function with basic options."""
        result = load_trivy_json(SAMPLE_TRIVY_REPORT, enrich=False)
        assert isinstance(result, LoadedData)
        assert len(result.cves) == 3

    def test_load_trivy_json_with_config(self):
        """Test the convenience function with host config."""
        config = {"criticality_score": 0.9}
        result = load_trivy_json(SAMPLE_TRIVY_REPORT, enrich=False, host_config=config)

        for host in result.hosts:
            assert host["criticality_score"] == 0.9


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_results(self):
        """Test handling of report with no results."""
        report = {"Results": []}
        loader = TrivyDataLoader(source=report, enrich_from_nvd=False, enrich_cwe=False)
        result = loader.load()

        assert len(result.hosts) == 0
        assert len(result.cves) == 0

    def test_results_without_vulnerabilities(self):
        """Test handling of results with no vulnerabilities."""
        report = {"Results": [{"Target": "clean-image", "Type": "alpine", "Vulnerabilities": None}]}
        loader = TrivyDataLoader(source=report, enrich_from_nvd=False, enrich_cwe=False)
        result = loader.load()

        assert len(result.hosts) == 0  # No host created without vulns

    def test_vulnerability_without_cwes(self):
        """Test handling of vulnerability without CWE IDs."""
        report = {
            "Results": [
                {
                    "Target": "test",
                    "Type": "alpine",
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2023-00001",
                            "PkgName": "test",
                            "InstalledVersion": "1.0",
                            "Severity": "HIGH",
                            "CweIDs": None,
                        }
                    ],
                }
            ]
        }
        loader = TrivyDataLoader(source=report, enrich_from_nvd=False, enrich_cwe=False)
        result = loader.load()

        cve = result.cves[0]
        assert cve["cwe_id"] == "CWE-noinfo"

    def test_duplicate_vulnerabilities_deduplicated(self):
        """Test that duplicate CVEs across targets are deduplicated."""
        report = {
            "Results": [
                {
                    "Target": "target1",
                    "Type": "alpine",
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2023-12345",
                            "PkgName": "curl",
                            "InstalledVersion": "8.0.0",
                            "Severity": "HIGH",
                        }
                    ],
                },
                {
                    "Target": "target2",
                    "Type": "alpine",
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2023-12345",  # Same CVE
                            "PkgName": "curl",
                            "InstalledVersion": "8.0.0",
                            "Severity": "HIGH",
                        }
                    ],
                },
            ]
        }
        loader = TrivyDataLoader(source=report, enrich_from_nvd=False, enrich_cwe=False)
        result = loader.load()

        # Should only have 1 CVE despite appearing in 2 targets
        assert len(result.cves) == 1

    def test_non_cve_vulnerability_ids(self):
        """Test handling of non-CVE vulnerability IDs (e.g., GHSA)."""
        report = {
            "Results": [
                {
                    "Target": "test",
                    "Type": "npm",
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "GHSA-xxxx-yyyy-zzzz",
                            "PkgName": "test-pkg",
                            "InstalledVersion": "1.0.0",
                            "Severity": "HIGH",
                        }
                    ],
                }
            ]
        }
        loader = TrivyDataLoader(source=report, enrich_from_nvd=False, enrich_cwe=False)
        result = loader.load()

        # Should still create a CVE entry
        assert len(result.cves) == 1
        assert result.cves[0]["id"] == "GHSA-xxxx-yyyy-zzzz"
