"""
Tests for Trivy upload and data management API endpoints.
"""

import json
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


# Sample Trivy report for testing
SAMPLE_TRIVY_REPORT = {
    "Results": [
        {
            "Target": "alpine:3.18",
            "Type": "alpine",
            "Vulnerabilities": [
                {
                    "VulnerabilityID": "CVE-2023-12345",
                    "PkgName": "curl",
                    "InstalledVersion": "8.0.0",
                    "Severity": "HIGH",
                    "CweIDs": ["CWE-79"],
                }
            ],
        }
    ]
}

# Sample deployment config for testing
SAMPLE_DEPLOYMENT_CONFIG = {
    "version": "1.0",
    "name": "Test Deployment",
    "hosts": [
        {
            "id": "web-server",
            "os_family": "Linux",
            "criticality_score": 0.7,
            "subnet_id": "dmz",
            "trivy_targets": ["alpine:*"],
        }
    ],
}


@pytest.fixture
def client():
    """Create a test client with fresh state."""
    # Reset global state before each test
    from src.viz import app as app_module
    app_module.uploaded_trivy_data = []
    app_module.uploaded_deployment_config = None
    app_module.current_data_source = "mock"

    return TestClient(app_module.app)


class TestTrivyUploadEndpoints:
    """Tests for Trivy data upload endpoints."""

    def test_upload_trivy_json_direct(self, client):
        """Test uploading Trivy JSON directly."""
        response = client.post(
            "/api/upload/trivy/json",
            json=SAMPLE_TRIVY_REPORT
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["total_uploaded"] == 1

    def test_upload_trivy_json_file(self, client):
        """Test uploading Trivy JSON as file."""
        json_content = json.dumps(SAMPLE_TRIVY_REPORT)
        response = client.post(
            "/api/upload/trivy",
            files={"file": ("trivy.json", json_content, "application/json")}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_upload_invalid_trivy_json(self, client):
        """Test that invalid Trivy JSON is rejected."""
        response = client.post(
            "/api/upload/trivy/json",
            json={"invalid": "data"}
        )
        assert response.status_code == 400
        assert "Results" in response.json()["detail"]

    def test_upload_multiple_trivy_files(self, client):
        """Test uploading multiple Trivy files."""
        # Upload first file
        response1 = client.post(
            "/api/upload/trivy/json",
            json=SAMPLE_TRIVY_REPORT
        )
        assert response1.json()["total_uploaded"] == 1

        # Upload second file
        response2 = client.post(
            "/api/upload/trivy/json",
            json=SAMPLE_TRIVY_REPORT
        )
        assert response2.json()["total_uploaded"] == 2

    def test_clear_trivy_uploads(self, client):
        """Test clearing uploaded Trivy data."""
        # Upload some data
        client.post("/api/upload/trivy/json", json=SAMPLE_TRIVY_REPORT)

        # Clear it
        response = client.delete("/api/data/trivy")
        assert response.status_code == 200

        # Check status
        status = client.get("/api/data/status").json()
        assert status["trivy_uploads"] == 0


class TestDeploymentConfigEndpoints:
    """Tests for deployment configuration upload endpoints."""

    def test_upload_deployment_json(self, client):
        """Test uploading deployment config as JSON."""
        response = client.post(
            "/api/upload/deployment/json",
            json=SAMPLE_DEPLOYMENT_CONFIG
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["hosts"] == 1

    def test_upload_deployment_yaml(self, client):
        """Test uploading deployment config as YAML file."""
        import yaml
        yaml_content = yaml.dump(SAMPLE_DEPLOYMENT_CONFIG)
        response = client.post(
            "/api/upload/deployment",
            files={"file": ("deployment.yaml", yaml_content, "application/x-yaml")}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_upload_invalid_deployment(self, client):
        """Test that invalid deployment config is handled."""
        response = client.post(
            "/api/upload/deployment/json",
            json={"hosts": [{"id": "test", "criticality_score": 2.0}]}  # Invalid score
        )
        assert response.status_code == 400  # Validation error


class TestDataStatusEndpoint:
    """Tests for data status endpoint."""

    def test_get_data_status_initial(self, client):
        """Test initial data status."""
        response = client.get("/api/data/status")
        assert response.status_code == 200
        data = response.json()
        assert data["current_source"] == "mock"
        assert data["trivy_uploads"] == 0
        assert data["has_deployment_config"] is False

    def test_get_data_status_after_upload(self, client):
        """Test data status after uploads."""
        # Upload Trivy data
        client.post("/api/upload/trivy/json", json=SAMPLE_TRIVY_REPORT)

        # Upload deployment config
        client.post("/api/upload/deployment/json", json=SAMPLE_DEPLOYMENT_CONFIG)

        response = client.get("/api/data/status")
        data = response.json()
        assert data["trivy_uploads"] == 1
        assert data["has_deployment_config"] is True
        assert data["deployment_hosts"] == 1


class TestRebuildEndpoint:
    """Tests for graph rebuild endpoint."""

    def test_rebuild_requires_trivy_data(self, client):
        """Test that rebuild fails without Trivy data."""
        response = client.post("/api/data/rebuild")
        assert response.status_code == 400
        assert "No Trivy data" in response.json()["detail"]

    @patch("src.viz.app.load_trivy_json")
    def test_rebuild_with_trivy_only(self, mock_load_trivy, client):
        """Test rebuilding with Trivy data only."""
        from src.data.loaders import LoadedData

        # Mock the load function
        mock_load_trivy.return_value = LoadedData(
            hosts=[{"id": "test-host", "os_family": "Linux", "criticality_score": 0.5, "subnet_id": "default"}],
            cpes=[{"id": "cpe:2.3:a:test:test:1.0:*", "vendor": "test", "product": "test", "version": "1.0"}],
            cves=[],
            cwes=[],
            host_cpe_map={"test-host": ["cpe:2.3:a:test:test:1.0:*"]},
            network_edges=[],
        )

        # Upload Trivy data
        client.post("/api/upload/trivy/json", json=SAMPLE_TRIVY_REPORT)

        # Rebuild without enrichment
        response = client.post("/api/data/rebuild?enrich=false&use_deployment=false")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["source"] == "trivy"

    @patch("src.viz.app.DeploymentLoader")
    def test_rebuild_with_deployment(self, mock_loader_class, client):
        """Test rebuilding with deployment config."""
        from src.data.loaders import LoadedData

        # Mock the loader
        mock_loader = MagicMock()
        mock_loader.load.return_value = LoadedData(
            hosts=[{"id": "web-server", "os_family": "Linux", "criticality_score": 0.7, "subnet_id": "dmz"}],
            cpes=[{"id": "cpe:2.3:a:test:test:1.0:*", "vendor": "test", "product": "test", "version": "1.0"}],
            cves=[],
            cwes=[],
            host_cpe_map={"web-server": ["cpe:2.3:a:test:test:1.0:*"]},
            network_edges=[],
        )
        mock_loader_class.return_value = mock_loader

        # Upload both Trivy and deployment
        client.post("/api/upload/trivy/json", json=SAMPLE_TRIVY_REPORT)
        client.post("/api/upload/deployment/json", json=SAMPLE_DEPLOYMENT_CONFIG)

        # Rebuild
        response = client.post("/api/data/rebuild?enrich=false")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["source"] == "deployment"


class TestResetEndpoint:
    """Tests for reset endpoint."""

    def test_reset_clears_data(self, client):
        """Test that reset clears all uploaded data."""
        # Upload some data
        client.post("/api/upload/trivy/json", json=SAMPLE_TRIVY_REPORT)
        client.post("/api/upload/deployment/json", json=SAMPLE_DEPLOYMENT_CONFIG)

        # Reset
        response = client.post("/api/data/reset")
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "mock"

        # Verify data is cleared
        status = client.get("/api/data/status").json()
        assert status["current_source"] == "mock"
        assert status["trivy_uploads"] == 0
        assert status["has_deployment_config"] is False


class TestExistingEndpoints:
    """Tests to verify existing endpoints still work."""

    def test_get_graph(self, client):
        """Test that /api/graph still works."""
        response = client.get("/api/graph")
        assert response.status_code == 200
        data = response.json()
        assert "elements" in data

    def test_get_stats(self, client):
        """Test that /api/stats still works."""
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_nodes" in data

    def test_get_config(self, client):
        """Test that /api/config still works."""
        response = client.get("/api/config")
        assert response.status_code == 200
