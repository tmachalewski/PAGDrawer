"""
Trivy JSON data loader.

Loads and transforms Trivy vulnerability scan results into the normalized
LoadedData format for attack graph generation.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ..schemas.trivy import (
    TrivyReport,
    Vulnerability,
    get_cvss_score,
    get_cvss_vector,
)
from .base import DataLoader, DataLoadError, LoadedData
from .cwe_fetcher import CWEFetcher
from .nvd_fetcher import NVDFetcher


class TrivyDataLoader(DataLoader):
    """Loads vulnerability data from Trivy JSON scan results.

    This loader parses Trivy's JSON output format and transforms it into
    the normalized LoadedData structure. It can optionally enrich the data
    by fetching additional information from NVD and CWE databases.

    Args:
        source: Path to Trivy JSON file or dict containing parsed JSON.
        enrich_from_nvd: Whether to fetch missing CVE data from NVD API.
        enrich_cwe: Whether to fetch CWE technical impact mappings.
        host_config: Optional host configuration overrides.
            - os_family: Override OS family detection (default: auto-detect)
            - criticality_score: Default criticality (default: 0.5)
            - subnet_id: Subnet identifier (default: "default")
        nvd_api_key: Optional NVD API key for higher rate limits.
    """

    def __init__(
        self,
        source: Any,
        enrich_from_nvd: bool = True,
        enrich_cwe: bool = True,
        host_config: Optional[Dict[str, Any]] = None,
        nvd_api_key: Optional[str] = None,
    ):
        self._source = source
        self._enrich_from_nvd = enrich_from_nvd
        self._enrich_cwe = enrich_cwe
        self._host_config = host_config or {}
        self._nvd_api_key = nvd_api_key

        # Lazily initialized fetchers
        self._nvd_fetcher: Optional[NVDFetcher] = None
        self._cwe_fetcher: Optional[CWEFetcher] = None

        # Track unique items during loading
        self._seen_cpes: Set[str] = set()
        self._seen_cves: Set[str] = set()
        self._seen_cwes: Set[str] = set()

    @property
    def nvd_fetcher(self) -> NVDFetcher:
        """Lazy initialization of NVD fetcher."""
        if self._nvd_fetcher is None:
            self._nvd_fetcher = NVDFetcher(api_key=self._nvd_api_key)
        return self._nvd_fetcher

    @property
    def cwe_fetcher(self) -> CWEFetcher:
        """Lazy initialization of CWE fetcher."""
        if self._cwe_fetcher is None:
            self._cwe_fetcher = CWEFetcher()
        return self._cwe_fetcher

    def validate_source(self) -> bool:
        """Validate that the Trivy JSON source is accessible and valid."""
        try:
            if isinstance(self._source, dict):
                # Already parsed JSON
                TrivyReport.model_validate(self._source)
                return True
            elif isinstance(self._source, (str, Path)):
                path = Path(self._source)
                if not path.exists():
                    return False
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                TrivyReport.model_validate(data)
                return True
            return False
        except Exception:
            return False

    def load(self) -> LoadedData:
        """Load and transform Trivy scan results into LoadedData format."""
        # Parse the source
        report = self._parse_source()

        # Reset tracking sets
        self._seen_cpes.clear()
        self._seen_cves.clear()
        self._seen_cwes.clear()

        # Build data structures
        hosts: List[Dict[str, Any]] = []
        cpes: List[Dict[str, Any]] = []
        cves: List[Dict[str, Any]] = []
        cwes: List[Dict[str, Any]] = []
        host_cpe_map: Dict[str, List[str]] = {}
        network_edges: List[Tuple[str, str]] = []

        # Process each scan result (target)
        for result in report.Results:
            if not result.Vulnerabilities:
                continue

            # Create host from target
            host_id = self._generate_host_id(result.Target, report.ArtifactName)
            host = self._create_host(host_id, result.Target, result.Type)
            hosts.append(host)
            host_cpe_map[host_id] = []

            # Process vulnerabilities
            for vuln in result.Vulnerabilities:
                # Create CPE from package info
                cpe_id = self._create_cpe_id(vuln.PkgName, vuln.InstalledVersion, result.Type)

                if cpe_id not in self._seen_cpes:
                    self._seen_cpes.add(cpe_id)
                    cpe = self._create_cpe(cpe_id, vuln.PkgName, vuln.InstalledVersion, result.Type)
                    cpes.append(cpe)

                # Map CPE to host
                if cpe_id not in host_cpe_map[host_id]:
                    host_cpe_map[host_id].append(cpe_id)

                # Create CVE entry
                if vuln.VulnerabilityID not in self._seen_cves:
                    self._seen_cves.add(vuln.VulnerabilityID)
                    cve = self._create_cve(vuln, cpe_id)
                    cves.append(cve)

                    # Process CWE IDs
                    if vuln.CweIDs:
                        for cwe_id in vuln.CweIDs:
                            if cwe_id not in self._seen_cwes:
                                self._seen_cwes.add(cwe_id)
                                cwe = self._create_cwe(cwe_id)
                                cwes.append(cwe)

        # Create default network edges (all hosts connected for now)
        # This can be customized based on deployment config
        if len(hosts) > 1:
            for i, h1 in enumerate(hosts):
                for h2 in hosts[i + 1 :]:
                    network_edges.append((h1["id"], h2["id"]))

        return LoadedData(
            hosts=hosts,
            cpes=cpes,
            cves=cves,
            cwes=cwes,
            host_cpe_map=host_cpe_map,
            network_edges=network_edges,
        )

    def _parse_source(self) -> TrivyReport:
        """Parse the Trivy JSON source into a TrivyReport."""
        try:
            if isinstance(self._source, dict):
                return TrivyReport.model_validate(self._source)
            elif isinstance(self._source, (str, Path)):
                path = Path(self._source)
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return TrivyReport.model_validate(data)
            else:
                raise DataLoadError(f"Unsupported source type: {type(self._source)}")
        except json.JSONDecodeError as e:
            raise DataLoadError(f"Invalid JSON: {e}")
        except Exception as e:
            raise DataLoadError(f"Failed to parse Trivy report: {e}")

    def _generate_host_id(self, target: str, artifact_name: Optional[str]) -> str:
        """Generate a unique host ID from target and artifact info."""
        base = artifact_name or target
        # Create a short hash for uniqueness
        hash_suffix = hashlib.md5(target.encode()).hexdigest()[:8]
        # Clean the name for use as ID
        clean_name = re.sub(r"[^a-zA-Z0-9_-]", "_", base.split("/")[-1].split(":")[0])
        return f"host_{clean_name}_{hash_suffix}"

    def _create_host(self, host_id: str, target: str, target_type: Optional[str]) -> Dict[str, Any]:
        """Create a host entry from target information."""
        # Detect OS family from target type
        os_family = self._host_config.get("os_family")
        if not os_family:
            os_family = self._detect_os_family(target, target_type)

        return {
            "id": host_id,
            "os_family": os_family,
            "criticality_score": self._host_config.get("criticality_score", 0.5),
            "subnet_id": self._host_config.get("subnet_id", "default"),
            "target": target,
            "target_type": target_type,
        }

    def _detect_os_family(self, target: str, target_type: Optional[str]) -> str:
        """Detect OS family from target and type information."""
        target_lower = target.lower()
        type_lower = (target_type or "").lower()

        # Check for common OS indicators
        linux_indicators = ["alpine", "debian", "ubuntu", "centos", "rhel", "fedora", "linux", "amazon"]
        windows_indicators = ["windows", "win32", "win64", "microsoft"]

        for indicator in linux_indicators:
            if indicator in target_lower or indicator in type_lower:
                return "Linux"

        for indicator in windows_indicators:
            if indicator in target_lower or indicator in type_lower:
                return "Windows"

        # Default to Linux for containers
        if type_lower in ["os-pkgs", "library", "apk", "apt", "yum", "dnf"]:
            return "Linux"

        return "Unknown"

    def _create_cpe_id(self, pkg_name: str, version: str, pkg_type: Optional[str]) -> str:
        """Create a CPE 2.3 URI from package information."""
        # Normalize package name for CPE
        vendor = self._guess_vendor(pkg_name, pkg_type)
        product = re.sub(r"[^a-zA-Z0-9_-]", "_", pkg_name.lower())
        version_clean = re.sub(r"[^a-zA-Z0-9._-]", "_", version)

        return f"cpe:2.3:a:{vendor}:{product}:{version_clean}:*:*:*:*:*:*:*"

    def _guess_vendor(self, pkg_name: str, pkg_type: Optional[str]) -> str:
        """Guess vendor name from package name and type."""
        # Common vendor mappings
        vendor_patterns = {
            r"^lib": "gnu",
            r"^python-|^py-": "python",
            r"^node-|^npm-": "nodejs",
            r"^golang-|^go-": "golang",
            r"^ruby-|^gem-": "ruby",
            r"^php-": "php",
            r"^java-|^maven-": "java",
        }

        for pattern, vendor in vendor_patterns.items():
            if re.match(pattern, pkg_name.lower()):
                return vendor

        # Use package type as vendor hint
        type_vendors = {
            "npm": "nodejs",
            "pip": "python",
            "gem": "ruby",
            "cargo": "rust",
            "go": "golang",
            "maven": "maven",
            "nuget": "microsoft",
        }

        if pkg_type and pkg_type.lower() in type_vendors:
            return type_vendors[pkg_type.lower()]

        # Default to package name as vendor
        return re.sub(r"[^a-zA-Z0-9_-]", "_", pkg_name.lower().split("-")[0])

    def _create_cpe(self, cpe_id: str, pkg_name: str, version: str, pkg_type: Optional[str]) -> Dict[str, Any]:
        """Create a CPE entry from package information."""
        vendor = self._guess_vendor(pkg_name, pkg_type)
        product = re.sub(r"[^a-zA-Z0-9_-]", "_", pkg_name.lower())

        return {
            "id": cpe_id,
            "vendor": vendor,
            "product": product,
            "version": version,
            "pkg_type": pkg_type,
        }

    def _create_cve(self, vuln: Vulnerability, cpe_id: str) -> Dict[str, Any]:
        """Create a CVE entry from Trivy vulnerability data."""
        cve_id = vuln.VulnerabilityID

        # Get CVSS data from Trivy
        cvss_vector = get_cvss_vector(vuln)
        cvss_score = get_cvss_score(vuln)

        # Get description
        description = vuln.Description or vuln.Title or f"Vulnerability {cve_id}"

        # Determine CWE ID
        cwe_id = vuln.CweIDs[0] if vuln.CweIDs else "CWE-noinfo"

        # Get technical impact from CWE
        technical_impact = "Varies"
        if self._enrich_cwe and cwe_id != "CWE-noinfo":
            technical_impact = self.cwe_fetcher.get_primary_impact(
                cwe_id, severity=vuln.Severity, fetch_if_missing=True
            )

        # Try to enrich from NVD if missing data
        epss_score = 0.0
        if self._enrich_from_nvd and cve_id.startswith("CVE-"):
            nvd_data = self.nvd_fetcher.fetch_cve(cve_id, fetch_epss=True)
            if nvd_data:
                # Fill in missing CVSS
                if not cvss_vector and nvd_data.get("cvss_vector"):
                    cvss_vector = nvd_data["cvss_vector"]
                if not cvss_score and nvd_data.get("cvss_score"):
                    cvss_score = nvd_data["cvss_score"]
                # Get EPSS
                epss_score = nvd_data.get("epss_score", 0.0) or 0.0
                # Fill description if needed
                if description == f"Vulnerability {cve_id}" and nvd_data.get("description"):
                    description = nvd_data["description"]
                # Get CWE from NVD if not in Trivy
                if cwe_id == "CWE-noinfo" and nvd_data.get("cwe_ids"):
                    cwe_id = nvd_data["cwe_ids"][0]
                    if self._enrich_cwe:
                        technical_impact = self.cwe_fetcher.get_primary_impact(
                            cwe_id, severity=vuln.Severity, fetch_if_missing=True
                        )

        # Use default CVSS if still missing
        if not cvss_vector:
            cvss_vector = self._severity_to_default_cvss(vuln.Severity)

        return {
            "id": cve_id,
            "description": description,
            "epss_score": epss_score,
            "cvss_vector": cvss_vector,
            "cvss_score": cvss_score,
            "cpe_id": cpe_id,
            "cwe_id": cwe_id,
            "technical_impact": technical_impact,
            "severity": vuln.Severity,
            "fixed_version": vuln.FixedVersion,
            "references": vuln.References,
        }

    def _severity_to_default_cvss(self, severity: str) -> str:
        """Generate a default CVSS vector based on severity."""
        # These are reasonable defaults based on severity
        defaults = {
            "CRITICAL": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
            "HIGH": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            "MEDIUM": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:L/A:L",
            "LOW": "CVSS:3.1/AV:L/AC:H/PR:L/UI:R/S:U/C:L/I:N/A:N",
            "UNKNOWN": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N",
        }
        return defaults.get(severity.upper(), defaults["UNKNOWN"])

    def _create_cwe(self, cwe_id: str) -> Dict[str, Any]:
        """Create a CWE entry, optionally fetching details."""
        # Normalize CWE ID format
        if not cwe_id.startswith("CWE-"):
            cwe_id = f"CWE-{cwe_id}"

        # Default values
        name = f"Weakness {cwe_id}"
        description = f"Security weakness identified as {cwe_id}"

        # Try to get more details from CWE fetcher cache
        if self._enrich_cwe:
            # The CWE fetcher doesn't store name/description, but we can
            # derive some info from the technical impacts
            impacts = self.cwe_fetcher.get_technical_impacts(cwe_id, fetch_if_missing=True)
            if impacts:
                name = f"{cwe_id} ({', '.join(impacts[:2])})"

        return {
            "id": cwe_id,
            "name": name,
            "description": description,
        }


def load_trivy_json(
    source: Any,
    enrich: bool = True,
    host_config: Optional[Dict[str, Any]] = None,
    nvd_api_key: Optional[str] = None,
) -> LoadedData:
    """Convenience function to load Trivy JSON data.

    Args:
        source: Path to Trivy JSON file or parsed JSON dict.
        enrich: Whether to enrich data from NVD/CWE sources.
        host_config: Optional host configuration overrides.
        nvd_api_key: Optional NVD API key.

    Returns:
        LoadedData instance with parsed vulnerability data.
    """
    loader = TrivyDataLoader(
        source=source,
        enrich_from_nvd=enrich,
        enrich_cwe=enrich,
        host_config=host_config,
        nvd_api_key=nvd_api_key,
    )
    return loader.load()
