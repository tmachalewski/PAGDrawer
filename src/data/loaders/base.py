"""
Base classes for data loaders.

Provides abstract interface for loading vulnerability data from various sources.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple


@dataclass
class LoadedData:
    """Container for vulnerability data loaded from any source.

    This dataclass represents the normalized format that all data loaders
    must produce, matching the structure expected by KnowledgeGraphBuilder.
    """

    hosts: List[Dict[str, Any]] = field(default_factory=list)
    """List of host configurations.
    Each host dict must have:
        - id: str (unique identifier)
        - os_family: str (e.g., "Linux", "Windows")
        - criticality_score: float (0.0-1.0)
        - subnet_id: str (network segment identifier)
    """

    cpes: List[Dict[str, Any]] = field(default_factory=list)
    """List of CPE (software) entries.
    Each CPE dict must have:
        - id: str (full CPE URI, e.g., "cpe:2.3:a:vendor:product:version:*")
        - vendor: str
        - product: str
        - version: str
    Optional:
        - edition: str
    """

    cves: List[Dict[str, Any]] = field(default_factory=list)
    """List of CVE (vulnerability) entries.
    Each CVE dict must have:
        - id: str (e.g., "CVE-2021-44228")
        - description: str
        - epss_score: float (0.0-1.0)
        - cvss_vector: str (CVSS 3.1 format)
        - cpe_id: str (reference to affected CPE)
        - cwe_id: str (e.g., "CWE-78")
        - technical_impact: str (for consensual matrix transformation)
    """

    cwes: List[Dict[str, Any]] = field(default_factory=list)
    """List of CWE (weakness category) entries.
    Each CWE dict must have:
        - id: str (e.g., "CWE-79")
        - name: str
        - description: str
    """

    host_cpe_map: Dict[str, List[str]] = field(default_factory=dict)
    """Mapping of host IDs to lists of CPE IDs running on that host."""

    network_edges: List[Tuple[str, str]] = field(default_factory=list)
    """List of (host_id, host_id) tuples representing network connectivity."""

    def validate(self) -> List[str]:
        """Validate the loaded data for completeness and consistency.

        Returns:
            List of validation error messages (empty if valid).
        """
        errors = []

        # Check required fields in hosts
        host_ids = set()
        for i, host in enumerate(self.hosts):
            if "id" not in host:
                errors.append(f"Host at index {i} missing 'id'")
            else:
                host_ids.add(host["id"])
            for field in ["os_family", "criticality_score", "subnet_id"]:
                if field not in host:
                    errors.append(f"Host '{host.get('id', i)}' missing '{field}'")

        # Check required fields in CPEs
        cpe_ids = set()
        for i, cpe in enumerate(self.cpes):
            if "id" not in cpe:
                errors.append(f"CPE at index {i} missing 'id'")
            else:
                cpe_ids.add(cpe["id"])
            for field in ["vendor", "product", "version"]:
                if field not in cpe:
                    errors.append(f"CPE '{cpe.get('id', i)}' missing '{field}'")

        # Check required fields in CVEs
        for i, cve in enumerate(self.cves):
            cve_id = cve.get("id", f"index_{i}")
            for field in ["id", "description", "epss_score", "cvss_vector", "cpe_id", "cwe_id", "technical_impact"]:
                if field not in cve:
                    errors.append(f"CVE '{cve_id}' missing '{field}'")

            # Check CPE reference exists
            if cve.get("cpe_id") and cve["cpe_id"] not in cpe_ids:
                errors.append(f"CVE '{cve_id}' references unknown CPE '{cve['cpe_id']}'")

        # Check required fields in CWEs
        cwe_ids = set()
        for i, cwe in enumerate(self.cwes):
            if "id" not in cwe:
                errors.append(f"CWE at index {i} missing 'id'")
            else:
                cwe_ids.add(cwe["id"])
            for field in ["name", "description"]:
                if field not in cwe:
                    errors.append(f"CWE '{cwe.get('id', i)}' missing '{field}'")

        # Check CWE references in CVEs
        for cve in self.cves:
            if cve.get("cwe_id") and cve["cwe_id"] not in cwe_ids:
                errors.append(f"CVE '{cve.get('id')}' references unknown CWE '{cve['cwe_id']}'")

        # Check host_cpe_map references
        for host_id, cpe_list in self.host_cpe_map.items():
            if host_id not in host_ids:
                errors.append(f"host_cpe_map references unknown host '{host_id}'")
            for cpe_id in cpe_list:
                if cpe_id not in cpe_ids:
                    errors.append(f"host_cpe_map['{host_id}'] references unknown CPE '{cpe_id}'")

        # Check network_edges references
        for src, dst in self.network_edges:
            if src not in host_ids:
                errors.append(f"network_edge references unknown source host '{src}'")
            if dst not in host_ids:
                errors.append(f"network_edge references unknown destination host '{dst}'")

        return errors

    def get_stats(self) -> Dict[str, int]:
        """Get statistics about the loaded data."""
        return {
            "hosts": len(self.hosts),
            "cpes": len(self.cpes),
            "cves": len(self.cves),
            "cwes": len(self.cwes),
            "host_cpe_mappings": sum(len(v) for v in self.host_cpe_map.values()),
            "network_edges": len(self.network_edges),
        }


class DataLoader(ABC):
    """Abstract base class for vulnerability data loaders.

    Implementations should load data from their respective sources
    and transform it into the normalized LoadedData format.
    """

    @abstractmethod
    def load(self) -> LoadedData:
        """Load and return normalized vulnerability data.

        Returns:
            LoadedData instance containing all vulnerability data.

        Raises:
            DataLoadError: If data cannot be loaded or parsed.
        """
        pass

    @abstractmethod
    def validate_source(self) -> bool:
        """Validate that the data source is accessible and valid.

        Returns:
            True if the source is valid and accessible.
        """
        pass

    def load_and_validate(self) -> LoadedData:
        """Load data and validate it.

        Returns:
            LoadedData instance that has passed validation.

        Raises:
            DataLoadError: If data cannot be loaded.
            DataValidationError: If loaded data fails validation.
        """
        data = self.load()
        errors = data.validate()
        if errors:
            raise DataValidationError(f"Data validation failed: {errors}")
        return data


class DataLoadError(Exception):
    """Raised when data cannot be loaded from a source."""
    pass


class DataValidationError(Exception):
    """Raised when loaded data fails validation."""
    pass
