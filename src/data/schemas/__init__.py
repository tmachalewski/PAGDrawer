"""
Pydantic schemas for data validation.

Contains schema definitions for Trivy JSON, NVD API responses,
CWE data, and deployment configuration.
"""

from .trivy import (
    SEVERITY_MAP,
    SEVERITY_TO_NUM,
    ScanMetadata,
    Result,
    TrivyReport,
    Vulnerability,
    get_cvss_score,
    get_cvss_vector,
)
from .deployment import (
    DeploymentConfig,
    HostConfig,
    SubnetConfig,
    NetworkEdgeConfig,
    EXAMPLE_CONFIG_YAML,
)

__all__ = [
    # Trivy schemas
    "TrivyReport",
    "Result",
    "Vulnerability",
    "ScanMetadata",
    "SEVERITY_MAP",
    "SEVERITY_TO_NUM",
    "get_cvss_vector",
    "get_cvss_score",
    # Deployment schemas
    "DeploymentConfig",
    "HostConfig",
    "SubnetConfig",
    "NetworkEdgeConfig",
    "EXAMPLE_CONFIG_YAML",
]
