"""
Tests for data loader abstraction.

Tests the LoadedData dataclass, DataLoader base class, and MockDataLoader.
"""

import pytest
from src.data.loaders import (
    DataLoader,
    LoadedData,
    DataLoadError,
    DataValidationError,
    MockDataLoader,
)
from src.graph.builder import KnowledgeGraphBuilder


class TestLoadedData:
    """Tests for the LoadedData dataclass."""

    def test_default_initialization(self):
        """LoadedData should initialize with empty collections."""
        data = LoadedData()
        assert data.hosts == []
        assert data.cpes == []
        assert data.cves == []
        assert data.cwes == []
        assert data.host_cpe_map == {}
        assert data.network_edges == []

    def test_initialization_with_data(self):
        """LoadedData should accept data on initialization."""
        hosts = [{"id": "h1", "os_family": "Linux", "criticality_score": 0.5, "subnet_id": "dmz"}]
        cpes = [{"id": "cpe:2.3:a:vendor:product:1.0:*", "vendor": "vendor", "product": "product", "version": "1.0"}]

        data = LoadedData(hosts=hosts, cpes=cpes)

        assert len(data.hosts) == 1
        assert len(data.cpes) == 1

    def test_validate_empty_data_passes(self):
        """Empty LoadedData should pass validation."""
        data = LoadedData()
        errors = data.validate()
        assert errors == []

    def test_validate_complete_data_passes(self):
        """Complete valid data should pass validation."""
        data = LoadedData(
            hosts=[
                {"id": "h1", "os_family": "Linux", "criticality_score": 0.5, "subnet_id": "dmz"}
            ],
            cpes=[
                {"id": "cpe:2.3:a:vendor:product:1.0:*", "vendor": "vendor", "product": "product", "version": "1.0"}
            ],
            cves=[
                {
                    "id": "CVE-2021-12345",
                    "description": "Test vulnerability",
                    "epss_score": 0.5,
                    "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                    "cpe_id": "cpe:2.3:a:vendor:product:1.0:*",
                    "cwe_id": "CWE-79",
                    "technical_impact": "Execute Unauthorized Code"
                }
            ],
            cwes=[
                {"id": "CWE-79", "name": "XSS", "description": "Cross-site scripting"}
            ],
            host_cpe_map={"h1": ["cpe:2.3:a:vendor:product:1.0:*"]},
            network_edges=[("h1", "h1")]
        )
        errors = data.validate()
        assert errors == []

    def test_validate_missing_host_id(self):
        """Validation should catch missing host id."""
        data = LoadedData(
            hosts=[{"os_family": "Linux", "criticality_score": 0.5, "subnet_id": "dmz"}]
        )
        errors = data.validate()
        assert any("missing 'id'" in e for e in errors)

    def test_validate_missing_host_fields(self):
        """Validation should catch missing host fields."""
        data = LoadedData(
            hosts=[{"id": "h1"}]
        )
        errors = data.validate()
        assert any("missing 'os_family'" in e for e in errors)
        assert any("missing 'criticality_score'" in e for e in errors)
        assert any("missing 'subnet_id'" in e for e in errors)

    def test_validate_missing_cpe_fields(self):
        """Validation should catch missing CPE fields."""
        data = LoadedData(
            cpes=[{"id": "cpe:test"}]
        )
        errors = data.validate()
        assert any("missing 'vendor'" in e for e in errors)
        assert any("missing 'product'" in e for e in errors)
        assert any("missing 'version'" in e for e in errors)

    def test_validate_missing_cve_fields(self):
        """Validation should catch missing CVE fields."""
        data = LoadedData(
            cves=[{"id": "CVE-2021-12345"}]
        )
        errors = data.validate()
        assert any("missing 'description'" in e for e in errors)
        assert any("missing 'epss_score'" in e for e in errors)
        assert any("missing 'cvss_vector'" in e for e in errors)
        assert any("missing 'cpe_id'" in e for e in errors)
        assert any("missing 'cwe_id'" in e for e in errors)
        assert any("missing 'technical_impact'" in e for e in errors)

    def test_validate_unknown_cpe_reference(self):
        """Validation should catch CVE referencing unknown CPE."""
        data = LoadedData(
            cves=[
                {
                    "id": "CVE-2021-12345",
                    "description": "Test",
                    "epss_score": 0.5,
                    "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                    "cpe_id": "cpe:unknown",
                    "cwe_id": "CWE-79",
                    "technical_impact": "Test"
                }
            ]
        )
        errors = data.validate()
        assert any("unknown CPE 'cpe:unknown'" in e for e in errors)

    def test_validate_unknown_cwe_reference(self):
        """Validation should catch CVE referencing unknown CWE."""
        data = LoadedData(
            cpes=[
                {"id": "cpe:test", "vendor": "v", "product": "p", "version": "1"}
            ],
            cves=[
                {
                    "id": "CVE-2021-12345",
                    "description": "Test",
                    "epss_score": 0.5,
                    "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                    "cpe_id": "cpe:test",
                    "cwe_id": "CWE-UNKNOWN",
                    "technical_impact": "Test"
                }
            ]
        )
        errors = data.validate()
        assert any("unknown CWE 'CWE-UNKNOWN'" in e for e in errors)

    def test_validate_unknown_host_in_cpe_map(self):
        """Validation should catch host_cpe_map referencing unknown host."""
        data = LoadedData(
            host_cpe_map={"unknown_host": ["cpe:test"]}
        )
        errors = data.validate()
        assert any("unknown host 'unknown_host'" in e for e in errors)

    def test_validate_unknown_cpe_in_host_map(self):
        """Validation should catch host_cpe_map referencing unknown CPE."""
        data = LoadedData(
            hosts=[{"id": "h1", "os_family": "Linux", "criticality_score": 0.5, "subnet_id": "dmz"}],
            host_cpe_map={"h1": ["cpe:unknown"]}
        )
        errors = data.validate()
        assert any("unknown CPE 'cpe:unknown'" in e for e in errors)

    def test_validate_unknown_host_in_network_edge(self):
        """Validation should catch network edges with unknown hosts."""
        data = LoadedData(
            network_edges=[("unknown_src", "unknown_dst")]
        )
        errors = data.validate()
        assert any("unknown source host" in e for e in errors)
        assert any("unknown destination host" in e for e in errors)

    def test_get_stats(self):
        """get_stats should return correct counts."""
        data = LoadedData(
            hosts=[{"id": "h1"}, {"id": "h2"}],
            cpes=[{"id": "c1"}],
            cves=[{"id": "cve1"}, {"id": "cve2"}, {"id": "cve3"}],
            cwes=[{"id": "cwe1"}],
            host_cpe_map={"h1": ["c1", "c2"], "h2": ["c3"]},
            network_edges=[("h1", "h2")]
        )
        stats = data.get_stats()

        assert stats["hosts"] == 2
        assert stats["cpes"] == 1
        assert stats["cves"] == 3
        assert stats["cwes"] == 1
        assert stats["host_cpe_mappings"] == 3
        assert stats["network_edges"] == 1


class TestMockDataLoader:
    """Tests for the MockDataLoader implementation."""

    def test_validate_source_returns_true(self):
        """MockDataLoader source is always valid."""
        loader = MockDataLoader()
        assert loader.validate_source() is True

    def test_load_returns_loaded_data(self):
        """MockDataLoader.load() should return LoadedData instance."""
        loader = MockDataLoader()
        data = loader.load()
        assert isinstance(data, LoadedData)

    def test_load_has_hosts(self):
        """Loaded mock data should contain hosts."""
        loader = MockDataLoader()
        data = loader.load()
        assert len(data.hosts) > 0
        assert all("id" in h for h in data.hosts)

    def test_load_has_cpes(self):
        """Loaded mock data should contain CPEs."""
        loader = MockDataLoader()
        data = loader.load()
        assert len(data.cpes) > 0
        assert all("id" in c for c in data.cpes)

    def test_load_has_cves(self):
        """Loaded mock data should contain CVEs."""
        loader = MockDataLoader()
        data = loader.load()
        assert len(data.cves) > 0
        assert all("id" in c for c in data.cves)

    def test_load_has_cwes(self):
        """Loaded mock data should contain CWEs."""
        loader = MockDataLoader()
        data = loader.load()
        assert len(data.cwes) > 0
        assert all("id" in c for c in data.cwes)

    def test_load_has_host_cpe_map(self):
        """Loaded mock data should have host-to-CPE mappings."""
        loader = MockDataLoader()
        data = loader.load()
        assert len(data.host_cpe_map) > 0

    def test_load_has_network_edges(self):
        """Loaded mock data should have network edges."""
        loader = MockDataLoader()
        data = loader.load()
        assert len(data.network_edges) > 0
        assert all(isinstance(e, tuple) and len(e) == 2 for e in data.network_edges)

    def test_loaded_data_passes_validation(self):
        """Mock data should pass all validation checks."""
        loader = MockDataLoader()
        data = loader.load()
        errors = data.validate()
        assert errors == [], f"Validation errors: {errors}"

    def test_load_returns_copies(self):
        """Loaded data should be copies, not references to original."""
        loader = MockDataLoader()
        data1 = loader.load()
        data2 = loader.load()

        # Modify data1
        data1.hosts.append({"id": "new_host"})

        # data2 should not be affected
        assert len(data1.hosts) != len(data2.hosts)


class TestBuilderWithLoadedData:
    """Tests for KnowledgeGraphBuilder.load_from_data()."""

    def test_load_from_data_creates_graph(self):
        """load_from_data should create a populated graph."""
        loader = MockDataLoader()
        data = loader.load()

        builder = KnowledgeGraphBuilder()
        builder.load_from_data(data)

        assert builder.graph.number_of_nodes() > 0
        assert builder.graph.number_of_edges() > 0

    def test_load_from_data_matches_mock_data(self):
        """load_from_data should produce same graph as load_from_mock_data."""
        loader = MockDataLoader()
        data = loader.load()

        builder1 = KnowledgeGraphBuilder()
        builder1.load_from_mock_data()

        builder2 = KnowledgeGraphBuilder()
        builder2.load_from_data(data)

        # Should have same number of nodes and edges
        assert builder1.graph.number_of_nodes() == builder2.graph.number_of_nodes()
        assert builder1.graph.number_of_edges() == builder2.graph.number_of_edges()

    def test_load_from_data_creates_all_node_types(self):
        """load_from_data should create all node types."""
        loader = MockDataLoader()
        data = loader.load()

        builder = KnowledgeGraphBuilder()
        builder.load_from_data(data)

        node_types = set()
        for _, attrs in builder.graph.nodes(data=True):
            node_types.add(attrs.get("node_type"))

        assert "HOST" in node_types
        assert "CPE" in node_types
        assert "CVE" in node_types
        assert "CWE" in node_types
        assert "TI" in node_types
        assert "VC" in node_types
        assert "ATTACKER" in node_types

    def test_load_from_data_creates_two_layers(self):
        """load_from_data should create both L1 and L2 layers."""
        loader = MockDataLoader()
        data = loader.load()

        builder = KnowledgeGraphBuilder()
        builder.load_from_data(data)

        layers = set()
        for _, attrs in builder.graph.nodes(data=True):
            if "layer" in attrs:
                layers.add(attrs["layer"])

        assert "L1" in layers
        assert "L2" in layers

    def test_load_from_data_with_custom_data(self):
        """load_from_data should work with custom LoadedData."""
        custom_data = LoadedData(
            hosts=[
                {"id": "test-host", "os_family": "Linux", "criticality_score": 0.8, "subnet_id": "dmz"}
            ],
            cpes=[
                {"id": "cpe:2.3:a:test:app:1.0:*", "vendor": "test", "product": "app", "version": "1.0"}
            ],
            cves=[
                {
                    "id": "CVE-2021-99999",
                    "description": "Test vulnerability",
                    "epss_score": 0.9,
                    "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                    "cpe_id": "cpe:2.3:a:test:app:1.0:*",
                    "cwe_id": "CWE-78",
                    "technical_impact": "Execute Unauthorized Code"
                }
            ],
            cwes=[
                {"id": "CWE-78", "name": "Command Injection", "description": "OS command injection"}
            ],
            host_cpe_map={"test-host": ["cpe:2.3:a:test:app:1.0:*"]},
            network_edges=[]
        )

        builder = KnowledgeGraphBuilder()
        builder.load_from_data(custom_data)

        # Should have created nodes based on custom data
        assert builder.graph.number_of_nodes() > 0

        # Check that our custom host exists
        host_ids = [n for n, d in builder.graph.nodes(data=True) if d.get("node_type") == "HOST"]
        assert any("test-host" in h for h in host_ids)


class TestDataLoaderAndValidate:
    """Tests for the load_and_validate convenience method."""

    def test_load_and_validate_returns_data(self):
        """load_and_validate should return LoadedData when valid."""
        loader = MockDataLoader()
        data = loader.load_and_validate()
        assert isinstance(data, LoadedData)

    def test_load_and_validate_raises_on_invalid(self):
        """load_and_validate should raise DataValidationError on invalid data."""

        class InvalidLoader(DataLoader):
            def load(self):
                return LoadedData(
                    hosts=[{"id": "h1"}]  # Missing required fields
                )

            def validate_source(self):
                return True

        loader = InvalidLoader()
        with pytest.raises(DataValidationError):
            loader.load_and_validate()
