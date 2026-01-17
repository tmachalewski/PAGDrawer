"""
Pydantic schemas for Trivy JSON output validation.

Based on Trivy's JSON schema from https://trivy.dev/docs/latest/
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Vulnerability(BaseModel):
    """A single vulnerability entry from Trivy scan results."""
    model_config = {"extra": "allow"}

    VulnerabilityID: str
    PkgName: str
    PkgID: Optional[str] = None
    PkgPath: Optional[str] = None
    InstalledVersion: str
    FixedVersion: Optional[str] = None
    Layer: Optional[Dict[str, Any]] = None
    SeveritySource: Optional[str] = None
    PrimaryURL: Optional[str] = None
    DataSource: Optional[Dict[str, Any]] = None
    Title: Optional[str] = None
    Description: Optional[str] = None
    Severity: str = "UNKNOWN"
    CweIDs: Optional[List[str]] = None
    VendorSeverity: Optional[Dict[str, int]] = None
    CVSS: Optional[Dict[str, Any]] = None  # Dict of vendor -> CVSS data
    References: Optional[List[str]] = None
    PublishedDate: Optional[str] = None
    LastModifiedDate: Optional[str] = None


class Result(BaseModel):
    """A single scan result (target) from Trivy."""
    model_config = {"extra": "allow"}

    Target: str
    Class: Optional[str] = None
    Type: Optional[str] = None
    Vulnerabilities: Optional[List[Vulnerability]] = None
    MisconfSummary: Optional[Dict[str, Any]] = None
    Misconfigurations: Optional[List[Dict[str, Any]]] = None


class ScanMetadata(BaseModel):
    """Scan metadata from Trivy report."""
    model_config = {"extra": "allow"}

    ImageID: Optional[str] = None
    DiffIDs: Optional[List[str]] = None
    RepoTags: Optional[List[str]] = None
    RepoDigests: Optional[List[str]] = None
    ImageConfig: Optional[Dict[str, Any]] = None


class TrivyReport(BaseModel):
    """Root schema for Trivy JSON output."""
    model_config = {"extra": "allow"}

    SchemaVersion: Optional[int] = None
    CreatedAt: Optional[str] = None
    ArtifactName: Optional[str] = None
    ArtifactType: Optional[str] = None
    ScanMetadata: Optional[ScanMetadata] = None
    Results: List[Result] = Field(default_factory=list)


# Severity mapping: Trivy numeric to string
SEVERITY_MAP = {
    0: "UNKNOWN",
    1: "LOW",
    2: "MEDIUM",
    3: "HIGH",
    4: "CRITICAL",
}

# Reverse mapping: string to numeric
SEVERITY_TO_NUM = {v: k for k, v in SEVERITY_MAP.items()}


def get_cvss_vector(vuln: Vulnerability) -> Optional[str]:
    """Extract CVSS v3 vector string from vulnerability, preferring NVD."""
    if not vuln.CVSS:
        return None

    # Prefer NVD, then redhat, then any available
    for source in ["nvd", "redhat"]:
        if source in vuln.CVSS:
            cvss = vuln.CVSS[source]
            if isinstance(cvss, dict) and cvss.get("V3Vector"):
                return cvss["V3Vector"]

    # Try any source with V3Vector
    for cvss in vuln.CVSS.values():
        if isinstance(cvss, dict) and cvss.get("V3Vector"):
            return cvss["V3Vector"]

    return None


def get_cvss_score(vuln: Vulnerability) -> Optional[float]:
    """Extract CVSS v3 score from vulnerability, preferring NVD."""
    if not vuln.CVSS:
        return None

    for source in ["nvd", "redhat"]:
        if source in vuln.CVSS:
            cvss = vuln.CVSS[source]
            if isinstance(cvss, dict) and cvss.get("V3Score") is not None:
                return cvss["V3Score"]

    for cvss in vuln.CVSS.values():
        if isinstance(cvss, dict) and cvss.get("V3Score") is not None:
            return cvss["V3Score"]

    return None
