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
def client(mock_mongo):
    """Create a test client with fresh state.

    Depends on mock_mongo so endpoints that touch MongoDB (such as
    /api/data/rebuild) see an initialized in-memory database.
    """
    from src.viz import app as app_module
    app_module.uploaded_trivy_scans = []
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

    def test_rebuild_returns_job_id(self, client):
        """Rebuild is now async; the endpoint returns a job_id immediately."""
        client.post("/api/upload/trivy/json", json=SAMPLE_TRIVY_REPORT)
        response = client.post("/api/data/rebuild?enrich=false&use_deployment=false")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert "job_id" in data

    def test_rebuild_rejects_concurrent_jobs_with_409(self, mock_mongo, client):
        """A second rebuild while one is running should return 409 Conflict."""
        from src.data.jobs import JobManager
        # Start a fake running job directly in mongomock
        JobManager().create_job()

        client.post("/api/upload/trivy/json", json=SAMPLE_TRIVY_REPORT)
        response = client.post("/api/data/rebuild?enrich=false&use_deployment=false")
        assert response.status_code == 409
        assert "running_job_id" in response.json()["detail"]

    def test_rebuild_progress_endpoint_returns_job(self, mock_mongo, client):
        """GET /api/data/rebuild/progress/{job_id} returns the job document."""
        from src.data.jobs import JobManager
        job = JobManager().create_job(total_cves=10)
        response = client.get(f"/api/data/rebuild/progress/{job.job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job.job_id
        assert data["status"] == "running"
        assert data["total_cves"] == 10

    def test_rebuild_progress_unknown_job_returns_404(self, client):
        response = client.get("/api/data/rebuild/progress/nonexistent-id")
        assert response.status_code == 404

    def test_rebuild_cancel_requests_flag(self, mock_mongo, client):
        from src.data.jobs import JobManager
        jm = JobManager()
        job = jm.create_job()
        response = client.post(f"/api/data/rebuild/cancel/{job.job_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "cancel_requested"
        assert jm.is_cancelled(job.job_id)

    def test_rebuild_cancel_unknown_job_returns_404(self, client):
        response = client.post("/api/data/rebuild/cancel/nope")
        assert response.status_code == 404


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


class TestScanSelectionEndpoints:
    """Tests for scan selection and management endpoints."""

    def test_list_scans_empty(self, client):
        """Test listing scans when none uploaded."""
        response = client.get("/api/data/scans")
        assert response.status_code == 200
        data = response.json()
        assert data["scans"] == []

    def test_list_scans_after_upload(self, client):
        """Test listing scans after uploading."""
        # Upload a scan
        client.post("/api/upload/trivy/json", json=SAMPLE_TRIVY_REPORT)

        response = client.get("/api/data/scans")
        assert response.status_code == 200
        data = response.json()
        assert len(data["scans"]) == 1

        scan = data["scans"][0]
        assert "id" in scan
        assert "name" in scan
        assert "filename" in scan
        assert "uploaded_at" in scan
        assert "vuln_count" in scan
        assert scan["vuln_count"] == 1  # One vuln in sample

    def test_list_scans_exposes_trivy_metadata(self, client):
        """Trivy reproducibility fields (CreatedAt, RepoDigests, etc.) flow
        through into the /api/data/scans response."""
        report = {
            **SAMPLE_TRIVY_REPORT,
            "ArtifactName": "nginx:stable-trixie-perl",
            "ArtifactID": "sha256:cafef00d",
            "CreatedAt": "2025-10-29T14:23:11Z",
            "ReportID": "11111111-2222-3333-4444-555555555555",
            "Trivy": {"Version": "0.58.1"},
            "Metadata": {"RepoDigests": ["nginx@sha256:deadbeef"]},
        }
        client.post("/api/upload/trivy/json", json=report)

        scan = client.get("/api/data/scans").json()["scans"][0]
        assert scan["trivy_created_at"] == "2025-10-29T14:23:11Z"
        assert scan["trivy_repo_digest"] == "nginx@sha256:deadbeef"
        assert scan["trivy_artifact_id"] == "sha256:cafef00d"
        assert scan["trivy_report_id"] == "11111111-2222-3333-4444-555555555555"
        assert scan["trivy_version"] == "0.58.1"

    def test_list_scans_trivy_metadata_optional(self, client):
        """When Trivy fields are absent, the API exposes them as null
        rather than omitting the keys (stable schema)."""
        client.post("/api/upload/trivy/json", json=SAMPLE_TRIVY_REPORT)
        scan = client.get("/api/data/scans").json()["scans"][0]
        assert scan["trivy_created_at"] is None
        assert scan["trivy_repo_digest"] is None
        assert scan["trivy_artifact_id"] is None
        assert scan["trivy_report_id"] is None
        assert scan["trivy_version"] is None

    def test_list_scans_multiple_uploads(self, client):
        """Test listing multiple uploaded scans."""
        # Upload two scans
        client.post("/api/upload/trivy/json", json=SAMPLE_TRIVY_REPORT)
        client.post("/api/upload/trivy/json", json=SAMPLE_TRIVY_REPORT)

        response = client.get("/api/data/scans")
        data = response.json()
        assert len(data["scans"]) == 2

        # Each scan should have unique ID
        ids = [s["id"] for s in data["scans"]]
        assert len(set(ids)) == 2

    def test_delete_scan(self, client):
        """Test deleting a specific scan."""
        # Upload two scans
        client.post("/api/upload/trivy/json", json=SAMPLE_TRIVY_REPORT)
        client.post("/api/upload/trivy/json", json=SAMPLE_TRIVY_REPORT)

        # Get scan IDs
        scans = client.get("/api/data/scans").json()["scans"]
        assert len(scans) == 2
        scan_id = scans[0]["id"]

        # Delete first scan
        response = client.delete(f"/api/data/scans/{scan_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["remaining"] == 1

        # Verify only one scan left
        remaining = client.get("/api/data/scans").json()["scans"]
        assert len(remaining) == 1
        assert remaining[0]["id"] != scan_id

    def test_delete_nonexistent_scan(self, client):
        """Test deleting a scan that doesn't exist."""
        response = client.delete("/api/data/scans/nonexistent-id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @patch("src.viz.app.load_trivy_json")
    def test_rebuild_with_specific_scan_ids(self, mock_load_trivy, client):
        """Rebuild with specific scan_ids now returns a job_id immediately."""
        from src.data.loaders import LoadedData

        mock_load_trivy.return_value = LoadedData(
            hosts=[{"id": "test-host", "os_family": "Linux", "criticality_score": 0.5, "subnet_id": "default"}],
            cpes=[{"id": "cpe:2.3:a:test:test:1.0:*", "vendor": "test", "product": "test", "version": "1.0"}],
            cves=[],
            cwes=[],
            host_cpe_map={"test-host": ["cpe:2.3:a:test:test:1.0:*"]},
            network_edges=[],
        )

        client.post("/api/upload/trivy/json", json=SAMPLE_TRIVY_REPORT)
        client.post("/api/upload/trivy/json", json=SAMPLE_TRIVY_REPORT)

        scans = client.get("/api/data/scans").json()["scans"]
        first_scan_id = scans[0]["id"]

        response = client.post(
            "/api/data/rebuild",
            params={"enrich": "false", "use_deployment": "false", "scan_ids": first_scan_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert "job_id" in data

    @patch("src.viz.app.load_trivy_json")
    def test_rebuild_with_invalid_scan_ids(self, mock_load_trivy, client):
        """Test rebuilding with nonexistent scan IDs returns error."""
        from src.data.loaders import LoadedData
        mock_load_trivy.return_value = LoadedData(
            hosts=[], cpes=[], cves=[], cwes=[], host_cpe_map={}, network_edges=[]
        )

        # Upload a scan
        client.post("/api/upload/trivy/json", json=SAMPLE_TRIVY_REPORT)

        # Rebuild with invalid ID - should fail with 400
        response = client.post(
            "/api/data/rebuild",
            params={"enrich": "false", "scan_ids": "invalid-id-that-does-not-exist"}
        )
        assert response.status_code == 400
        assert "No matching scans" in response.json()["detail"]

    def test_upload_returns_scan_metadata(self, client):
        """Test that upload response includes scan metadata."""
        response = client.post("/api/upload/trivy/json", json=SAMPLE_TRIVY_REPORT)
        assert response.status_code == 200
        data = response.json()

        assert "scan_id" in data
        assert "name" in data
        assert "vuln_count" in data
        assert data["vuln_count"] == 1
