"""
Shared test fixtures for PAGDrawer tests.
"""

import pytest
from typing import Dict, List

# Import modules under test
from src.core.schema import NodeType, EdgeType, VCType
from src.core.config import GraphConfig
from src.graph.builder import KnowledgeGraphBuilder


# =============================================================================
# SAMPLE DATA FIXTURES
# =============================================================================

@pytest.fixture
def sample_cvss_vector():
    """Sample CVSS 3.1 vector string."""
    return "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"


@pytest.fixture
def sample_cvss_high_complexity():
    """CVSS vector with high complexity."""
    return "CVSS:3.1/AV:N/AC:H/PR:L/UI:R/S:C/C:L/I:L/A:N"


@pytest.fixture
def sample_cvss_local():
    """CVSS vector requiring local access."""
    return "CVSS:3.1/AV:L/AC:L/PR:H/UI:N/S:U/C:H/I:H/A:H"


@pytest.fixture
def sample_host_data():
    """Sample host node data."""
    return {
        "id": "test-host-1",
        "os_family": "Linux",
        "criticality_score": 0.8,
        "subnet_id": "dmz"
    }


@pytest.fixture
def sample_cpe_data():
    """Sample CPE node data."""
    return {
        "id": "cpe:2.3:a:apache:http_server:2.4.41",
        "vendor": "apache",
        "product": "http_server",
        "version": "2.4.41"
    }


@pytest.fixture
def sample_cve_data():
    """Sample CVE node data."""
    return {
        "id": "CVE-2021-44228",
        "description": "Log4j remote code execution vulnerability",
        "epss_score": 0.975,
        "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
        "cwe_ids": ["CWE-917"],
        "technical_impacts": ["Execute Unauthorized Code or Commands"]
    }


@pytest.fixture
def sample_cwe_data():
    """Sample CWE node data."""
    return {
        "id": "CWE-79",
        "name": "Cross-site Scripting (XSS)",
        "description": "Improper neutralization of input during web page generation"
    }


# =============================================================================
# GRAPH FIXTURES
# =============================================================================

@pytest.fixture
def default_config():
    """Default graph configuration."""
    return GraphConfig()


@pytest.fixture
def singular_config():
    """Configuration with all singular modes."""
    config = GraphConfig()
    for node_type in ["CPE", "CVE", "CWE", "TI", "VC"]:
        config.set_mode(node_type, "singular")
    return config


@pytest.fixture
def universal_config():
    """Configuration with all universal modes."""
    config = GraphConfig()
    for node_type in ["CPE", "CVE", "CWE", "TI", "VC"]:
        config.set_mode(node_type, "universal")
    return config


@pytest.fixture
def empty_graph_builder(default_config):
    """Empty graph builder instance."""
    return KnowledgeGraphBuilder(config=default_config)


@pytest.fixture
def loaded_graph_builder(default_config):
    """Graph builder with mock data loaded."""
    builder = KnowledgeGraphBuilder(config=default_config)
    builder.load_from_mock_data()
    return builder


# =============================================================================
# TECHNICAL IMPACT FIXTURES
# =============================================================================

@pytest.fixture
def sample_technical_impacts():
    """Sample technical impact strings."""
    return [
        "Execute Unauthorized Code or Commands",
        "Gain Privileges or Assume Identity",
        "Read Memory",
        "Bypass Protection Mechanism",
        "DoS: Crash, Exit, or Restart"
    ]
