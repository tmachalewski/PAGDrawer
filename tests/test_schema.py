"""
Tests for src/core/schema.py - Schema definitions and enums.
"""

import pytest
from src.core.schema import (
    NodeType, EdgeType, VCType,
    AVValue, PRValue, ACValue, UIValue,
    HostNode, CPENode, CVENode, CWENode, VCNode, Edge,
    create_vc_id, parse_cvss_vector
)


class TestNodeTypeEnum:
    """Tests for NodeType enum."""
    
    def test_has_all_node_types(self):
        """Verify all 6 node types exist."""
        expected = ["HOST", "CPE", "CVE", "CWE", "TI", "VC"]
        actual = [t.name for t in NodeType]
        assert sorted(actual) == sorted(expected)
    
    def test_node_type_count(self):
        """Verify exactly 6 node types."""
        assert len(NodeType) == 6


class TestEdgeTypeEnum:
    """Tests for EdgeType enum."""
    
    def test_has_static_edges(self):
        """Verify static edge types exist."""
        static_edges = ["RUNS", "HAS_VULN", "IS_INSTANCE_OF", "CONNECTED_TO", "HAS_IMPACT"]
        for edge in static_edges:
            assert hasattr(EdgeType, edge)
    
    def test_has_dynamic_edges(self):
        """Verify dynamic edge types exist."""
        dynamic_edges = ["ALLOWS_EXPLOIT", "YIELDS_STATE"]
        for edge in dynamic_edges:
            assert hasattr(EdgeType, edge)


class TestVCTypeEnum:
    """Tests for VCType enum."""
    
    def test_has_all_vc_types(self):
        """Verify all VC types exist."""
        expected = ["AV", "PR", "EX", "AC", "UI"]
        for vc in expected:
            assert hasattr(VCType, vc)
    
    def test_vc_type_values(self):
        """Verify VC type string values."""
        assert VCType.AV.value == "AttackVector"
        assert VCType.PR.value == "PrivilegesRequired"
        assert VCType.EX.value == "Exploited"


class TestValueEnums:
    """Tests for value enums (AV, PR, AC, UI)."""
    
    def test_av_values(self):
        """Test Attack Vector values."""
        assert AVValue.NETWORK.value == "N"
        assert AVValue.ADJACENT.value == "A"
        assert AVValue.LOCAL.value == "L"
        assert AVValue.PHYSICAL.value == "P"
    
    def test_pr_values(self):
        """Test Privileges Required values."""
        assert PRValue.NONE.value == "N"
        assert PRValue.LOW.value == "L"
        assert PRValue.HIGH.value == "H"
    
    def test_ac_values(self):
        """Test Attack Complexity values."""
        assert ACValue.LOW.value == "L"
        assert ACValue.HIGH.value == "H"
    
    def test_ui_values(self):
        """Test User Interaction values."""
        assert UIValue.NONE.value == "N"
        assert UIValue.REQUIRED.value == "R"


class TestNodeDataClasses:
    """Tests for node data classes."""
    
    def test_host_node_creation(self):
        """Test HostNode creation."""
        host = HostNode(
            id="host-1",
            os_family="Linux",
            criticality_score=0.8,
            subnet_id="dmz"
        )
        assert host.id == "host-1"
        assert host.node_type == NodeType.HOST
    
    def test_cpe_node_creation(self):
        """Test CPENode creation."""
        cpe = CPENode(
            id="cpe:2.3:a:apache:http_server:2.4.41",
            vendor="apache",
            product="http_server",
            version="2.4.41"
        )
        assert cpe.node_type == NodeType.CPE
        assert cpe.vendor == "apache"
    
    def test_cve_node_creation(self):
        """Test CVENode creation."""
        cve = CVENode(
            id="CVE-2021-44228",
            description="Test vulnerability",
            epss_score=0.9,
            cvss_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
        )
        assert cve.node_type == NodeType.CVE
        assert cve.epss_score == 0.9
    
    def test_cwe_node_creation(self):
        """Test CWENode creation."""
        cwe = CWENode(
            id="CWE-79",
            name="XSS",
            description="Cross-site scripting"
        )
        assert cwe.node_type == NodeType.CWE
    
    def test_vc_node_creation(self):
        """Test VCNode creation."""
        vc = VCNode(
            id="VC:AV:N",
            vc_type=VCType.AV,
            value="N"
        )
        assert vc.node_type == NodeType.VC
        assert vc.vc_type == VCType.AV


class TestHelperFunctions:
    """Tests for helper functions."""
    
    def test_create_vc_id(self):
        """Test VC ID generation."""
        assert create_vc_id(VCType.AV, "N") == "VC:AV:N"
        assert create_vc_id(VCType.PR, "H") == "VC:PR:H"
        assert create_vc_id(VCType.EX, "Y") == "VC:EX:Y"
    
    def test_parse_cvss_vector_full(self, sample_cvss_vector):
        """Test parsing complete CVSS vector."""
        result = parse_cvss_vector(sample_cvss_vector)
        assert result["AV"] == "N"
        assert result["AC"] == "L"
        assert result["PR"] == "N"
        assert result["UI"] == "N"
        assert result["C"] == "H"
        assert result["I"] == "H"
        assert result["A"] == "H"
    
    def test_parse_cvss_vector_empty(self):
        """Test parsing empty CVSS vector."""
        result = parse_cvss_vector("")
        assert result == {}
    
    def test_parse_cvss_vector_partial(self):
        """Test parsing partial CVSS vector."""
        result = parse_cvss_vector("AV:N/AC:L")
        assert result["AV"] == "N"
        assert result["AC"] == "L"
        assert "PR" not in result
