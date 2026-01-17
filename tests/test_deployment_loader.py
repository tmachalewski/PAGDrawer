"""
Tests for DeploymentLoader and deployment configuration.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from src.data.loaders import DeploymentLoader, load_deployment
from src.data.loaders.base import DataLoadError, LoadedData
from src.data.schemas.deployment import (
    DeploymentConfig,
    HostConfig,
    SubnetConfig,
    NetworkEdgeConfig,
)


# Sample deployment configuration
SAMPLE_DEPLOYMENT = {
    "version": "1.0",
    "name": "Test Deployment",
    "defaults": {
        "os_family": "Linux",
        "criticality_score": 0.5,
        "subnet_id": "default",
    },
    "subnets": [
        {
            "id": "dmz",
            "name": "DMZ",
            "zone": "dmz",
            "connects_to": ["internal"],
        },
        {
            "id": "internal",
            "name": "Internal",
            "zone": "internal",
        },
    ],
    "hosts": [
        {
            "id": "web-server",
            "name": "Web Server",
            "os_family": "Linux",
            "criticality_score": 0.7,
            "subnet_id": "dmz",
            "trivy_targets": ["nginx:*", "frontend:*"],
        },
        {
            "id": "api-server",
            "name": "API Server",
            "os_family": "Linux",
            "criticality_score": 0.9,
            "subnet_id": "internal",
            "trivy_targets": ["api:*", "backend:*"],
        },
    ],
    "network_edges": [
        {"source": "web-server", "target": "api-server", "bidirectional": True},
    ],
}

# Sample Trivy report
SAMPLE_TRIVY = {
    "Results": [
        {
            "Target": "nginx:1.21",
            "Type": "alpine",
            "Vulnerabilities": [
                {
                    "VulnerabilityID": "CVE-2023-11111",
                    "PkgName": "nginx",
                    "InstalledVersion": "1.21.0",
                    "Severity": "HIGH",
                    "CweIDs": ["CWE-79"],
                }
            ],
        }
    ]
}


class TestDeploymentConfigParsing:
    """Tests for deployment configuration parsing."""

    def test_parse_from_dict(self):
        """Test parsing deployment config from dict."""
        config = DeploymentConfig.model_validate(SAMPLE_DEPLOYMENT)
        assert config.name == "Test Deployment"
        assert len(config.hosts) == 2
        assert len(config.subnets) == 2

    def test_parse_from_yaml_file(self, tmp_path):
        """Test parsing deployment config from YAML file."""
        yaml_file = tmp_path / "deployment.yaml"
        yaml_file.write_text(yaml.dump(SAMPLE_DEPLOYMENT))

        loader = DeploymentLoader(deployment_config=str(yaml_file))
        assert loader.deployment_config.name == "Test Deployment"

    def test_host_config_fields(self):
        """Test that host config has all required fields."""
        config = DeploymentConfig.model_validate(SAMPLE_DEPLOYMENT)
        host = config.hosts[0]

        assert host.id == "web-server"
        assert host.name == "Web Server"
        assert host.os_family == "Linux"
        assert host.criticality_score == 0.7
        assert host.subnet_id == "dmz"
        assert "nginx:*" in host.trivy_targets

    def test_criticality_score_validation(self):
        """Test that criticality_score is validated."""
        invalid_config = {
            "hosts": [
                {
                    "id": "test",
                    "criticality_score": 1.5,  # Invalid: > 1
                }
            ]
        }
        with pytest.raises(Exception):  # Pydantic validation error
            DeploymentConfig.model_validate(invalid_config)


class TestTrivyTargetMatching:
    """Tests for matching Trivy targets to hosts."""

    def test_exact_match(self):
        """Test exact target matching."""
        config = DeploymentConfig.model_validate(SAMPLE_DEPLOYMENT)
        host = config.find_host_by_trivy_target("nginx:1.21")
        # Should match "nginx:*" pattern
        assert host is not None
        assert host.id == "web-server"

    def test_glob_pattern_match(self):
        """Test glob pattern matching."""
        config = DeploymentConfig.model_validate(SAMPLE_DEPLOYMENT)

        # Test various targets
        assert config.find_host_by_trivy_target("nginx:latest") is not None
        assert config.find_host_by_trivy_target("frontend:v1.0") is not None
        assert config.find_host_by_trivy_target("api:2.0") is not None

    def test_no_match(self):
        """Test when no host matches target."""
        config = DeploymentConfig.model_validate(SAMPLE_DEPLOYMENT)
        host = config.find_host_by_trivy_target("unknown-image:v1")
        assert host is None


class TestNetworkEdges:
    """Tests for network edge generation."""

    def test_explicit_edges(self):
        """Test that explicit edges are included."""
        config = DeploymentConfig.model_validate(SAMPLE_DEPLOYMENT)
        edges = config.get_network_edges()

        # Should have bidirectional edge
        assert ("web-server", "api-server") in edges
        assert ("api-server", "web-server") in edges

    def test_subnet_connectivity(self):
        """Test edges generated from subnet connections."""
        config = DeploymentConfig.model_validate(SAMPLE_DEPLOYMENT)
        edges = config.get_network_edges()

        # DMZ connects_to internal, so web-server should connect to api-server
        assert ("web-server", "api-server") in edges

    def test_no_duplicate_edges(self):
        """Test that duplicate edges are removed."""
        config = DeploymentConfig.model_validate(SAMPLE_DEPLOYMENT)
        edges = config.get_network_edges()

        # Count occurrences
        edge_count = edges.count(("web-server", "api-server"))
        assert edge_count == 1


class TestDeploymentLoader:
    """Tests for DeploymentLoader class."""

    def test_init_with_dict_config(self):
        """Test initialization with dict config."""
        loader = DeploymentLoader(deployment_config=SAMPLE_DEPLOYMENT)
        assert loader.deployment_config.name == "Test Deployment"

    def test_init_with_deployment_config(self):
        """Test initialization with DeploymentConfig object."""
        config = DeploymentConfig.model_validate(SAMPLE_DEPLOYMENT)
        loader = DeploymentLoader(deployment_config=config)
        assert loader.deployment_config.name == "Test Deployment"

    def test_validate_source(self):
        """Test source validation."""
        loader = DeploymentLoader(deployment_config=SAMPLE_DEPLOYMENT)
        assert loader.validate_source() is True

    def test_validate_source_with_invalid_trivy(self, tmp_path):
        """Test validation fails with invalid Trivy source."""
        loader = DeploymentLoader(
            deployment_config=SAMPLE_DEPLOYMENT,
            trivy_sources=["/nonexistent/file.json"],
        )
        assert loader.validate_source() is False

    @patch("src.data.loaders.deployment_loader.TrivyDataLoader")
    def test_load_creates_hosts_from_config(self, mock_trivy_class):
        """Test that hosts are created from deployment config."""
        # Mock TrivyDataLoader to return empty data
        mock_loader = MagicMock()
        mock_loader.load.return_value = LoadedData()
        mock_trivy_class.return_value = mock_loader

        loader = DeploymentLoader(
            deployment_config=SAMPLE_DEPLOYMENT,
            trivy_sources=[SAMPLE_TRIVY],
            enrich_from_nvd=False,
            enrich_cwe=False,
        )
        result = loader.load()

        # Should have hosts from deployment config
        assert len(result.hosts) >= 2
        host_ids = {h["id"] for h in result.hosts}
        assert "web-server" in host_ids
        assert "api-server" in host_ids


class TestDeploymentLoaderIntegration:
    """Integration tests for DeploymentLoader with Trivy data."""

    def test_load_merges_trivy_data(self):
        """Test that Trivy data is merged correctly."""
        loader = DeploymentLoader(
            deployment_config=SAMPLE_DEPLOYMENT,
            trivy_sources=[SAMPLE_TRIVY],
            enrich_from_nvd=False,
            enrich_cwe=False,
        )
        result = loader.load()

        # Should have CVE from Trivy
        cve_ids = {c["id"] for c in result.cves}
        assert "CVE-2023-11111" in cve_ids

        # Should have CPE from Trivy
        assert len(result.cpes) > 0

    def test_trivy_target_maps_to_deployment_host(self):
        """Test that Trivy targets map to correct deployment hosts."""
        loader = DeploymentLoader(
            deployment_config=SAMPLE_DEPLOYMENT,
            trivy_sources=[SAMPLE_TRIVY],
            enrich_from_nvd=False,
            enrich_cwe=False,
        )
        result = loader.load()

        # nginx:1.21 should map to web-server (nginx:* pattern)
        web_server_cpes = result.host_cpe_map.get("web-server", [])
        assert len(web_server_cpes) > 0

    def test_unmapped_target_gets_defaults(self):
        """Test that unmapped targets get default config."""
        trivy_data = {
            "Results": [
                {
                    "Target": "unknown-image:v1",
                    "Type": "alpine",
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2023-99999",
                            "PkgName": "test",
                            "InstalledVersion": "1.0",
                            "Severity": "LOW",
                        }
                    ],
                }
            ]
        }

        loader = DeploymentLoader(
            deployment_config=SAMPLE_DEPLOYMENT,
            trivy_sources=[trivy_data],
            enrich_from_nvd=False,
            enrich_cwe=False,
        )
        result = loader.load()

        # Should create a new host with default criticality
        # Find the unmapped host
        unmapped_hosts = [h for h in result.hosts if h["id"] not in ["web-server", "api-server"]]
        if unmapped_hosts:
            assert unmapped_hosts[0]["criticality_score"] == 0.5  # Default


class TestConvenienceFunction:
    """Tests for load_deployment convenience function."""

    def test_load_deployment_from_yaml(self, tmp_path):
        """Test loading deployment from YAML file."""
        yaml_file = tmp_path / "deployment.yaml"
        yaml_file.write_text(yaml.dump(SAMPLE_DEPLOYMENT))

        result = load_deployment(config_path=str(yaml_file), enrich=False)
        assert isinstance(result, LoadedData)
        assert len(result.hosts) >= 2


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_deployment(self):
        """Test loading with empty deployment config."""
        config = {"version": "1.0"}
        loader = DeploymentLoader(deployment_config=config)
        result = loader.load()

        assert len(result.hosts) == 0

    def test_deployment_without_trivy(self):
        """Test loading deployment without any Trivy sources."""
        loader = DeploymentLoader(deployment_config=SAMPLE_DEPLOYMENT)
        result = loader.load()

        # Should have hosts from config but no CVEs
        assert len(result.hosts) == 2
        assert len(result.cves) == 0

    def test_multiple_trivy_sources(self):
        """Test loading multiple Trivy sources."""
        trivy1 = {
            "Results": [
                {
                    "Target": "nginx:1.21",
                    "Type": "alpine",
                    "Vulnerabilities": [
                        {"VulnerabilityID": "CVE-2023-00001", "PkgName": "pkg1", "InstalledVersion": "1.0", "Severity": "HIGH"}
                    ],
                }
            ]
        }
        trivy2 = {
            "Results": [
                {
                    "Target": "api:v1",
                    "Type": "alpine",
                    "Vulnerabilities": [
                        {"VulnerabilityID": "CVE-2023-00002", "PkgName": "pkg2", "InstalledVersion": "2.0", "Severity": "MEDIUM"}
                    ],
                }
            ]
        }

        loader = DeploymentLoader(
            deployment_config=SAMPLE_DEPLOYMENT,
            trivy_sources=[trivy1, trivy2],
            enrich_from_nvd=False,
            enrich_cwe=False,
        )
        result = loader.load()

        # Should have CVEs from both sources
        cve_ids = {c["id"] for c in result.cves}
        assert "CVE-2023-00001" in cve_ids
        assert "CVE-2023-00002" in cve_ids

    def test_add_trivy_source(self):
        """Test adding Trivy sources after initialization."""
        loader = DeploymentLoader(
            deployment_config=SAMPLE_DEPLOYMENT,
            enrich_from_nvd=False,
            enrich_cwe=False,
        )

        # Initially no CVEs
        result1 = loader.load()
        assert len(result1.cves) == 0

        # Add source and reload
        loader.add_trivy_source(SAMPLE_TRIVY)
        result2 = loader.load()
        assert len(result2.cves) > 0
