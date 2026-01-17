"""
Deployment-aware data loader.

Combines Trivy scan results with deployment configuration to create
a complete attack graph data set with proper network topology.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from ..schemas.deployment import DeploymentConfig, HostConfig
from .base import DataLoader, DataLoadError, LoadedData
from .trivy_loader import TrivyDataLoader


class DeploymentLoader(DataLoader):
    """Loads vulnerability data using deployment configuration.

    This loader combines Trivy scan results with a deployment configuration
    to create a complete data set with proper host assignments, network
    topology, and criticality scores.

    Args:
        deployment_config: Path to YAML file or dict/DeploymentConfig object.
        trivy_sources: List of Trivy JSON sources (paths or dicts).
        enrich_from_nvd: Whether to fetch missing CVE data from NVD API.
        enrich_cwe: Whether to fetch CWE technical impact mappings.
        nvd_api_key: Optional NVD API key for higher rate limits.
    """

    def __init__(
        self,
        deployment_config: Union[str, Path, Dict[str, Any], DeploymentConfig],
        trivy_sources: Optional[List[Any]] = None,
        enrich_from_nvd: bool = True,
        enrich_cwe: bool = True,
        nvd_api_key: Optional[str] = None,
    ):
        self._deployment_config = self._parse_deployment_config(deployment_config)
        self._trivy_sources = trivy_sources or []
        self._enrich_from_nvd = enrich_from_nvd
        self._enrich_cwe = enrich_cwe
        self._nvd_api_key = nvd_api_key

    def _parse_deployment_config(
        self, config: Union[str, Path, Dict[str, Any], DeploymentConfig]
    ) -> DeploymentConfig:
        """Parse deployment configuration from various sources."""
        if isinstance(config, DeploymentConfig):
            return config
        elif isinstance(config, dict):
            return DeploymentConfig.model_validate(config)
        elif isinstance(config, (str, Path)):
            path = Path(config)
            if not path.exists():
                raise DataLoadError(f"Deployment config file not found: {path}")
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return DeploymentConfig.model_validate(data)
        else:
            raise DataLoadError(f"Unsupported config type: {type(config)}")

    def validate_source(self) -> bool:
        """Validate that all sources are accessible and valid."""
        # Deployment config already validated in constructor
        if not self._deployment_config:
            return False

        # Validate Trivy sources
        for source in self._trivy_sources:
            loader = TrivyDataLoader(
                source=source,
                enrich_from_nvd=False,
                enrich_cwe=False,
            )
            if not loader.validate_source():
                return False

        return True

    def load(self) -> LoadedData:
        """Load and merge all data sources according to deployment config."""
        # Initialize empty data
        all_hosts: Dict[str, Dict[str, Any]] = {}
        all_cpes: Dict[str, Dict[str, Any]] = {}
        all_cves: Dict[str, Dict[str, Any]] = {}
        all_cwes: Dict[str, Dict[str, Any]] = {}
        host_cpe_map: Dict[str, List[str]] = {}

        # Create hosts from deployment config
        for host_config in self._deployment_config.hosts:
            host = {
                "id": host_config.id,
                "name": host_config.name or host_config.id,
                "os_family": host_config.os_family,
                "criticality_score": host_config.criticality_score,
                "subnet_id": host_config.subnet_id,
            }
            all_hosts[host_config.id] = host
            host_cpe_map[host_config.id] = []

        # Process each Trivy source
        for source in self._trivy_sources:
            trivy_data = self._load_trivy_source(source)

            # Merge Trivy data into deployment topology
            for trivy_host in trivy_data.hosts:
                target = trivy_host.get("target", "")

                # Find matching deployment host
                host_config = self._deployment_config.find_host_by_trivy_target(target)

                if host_config:
                    # Map to existing deployment host
                    host_id = host_config.id

                    # Merge CPEs
                    trivy_host_id = trivy_host["id"]
                    if trivy_host_id in trivy_data.host_cpe_map:
                        for cpe_id in trivy_data.host_cpe_map[trivy_host_id]:
                            if cpe_id not in host_cpe_map.get(host_id, []):
                                host_cpe_map.setdefault(host_id, []).append(cpe_id)
                else:
                    # Create new host from Trivy data with defaults
                    host_id = trivy_host["id"]
                    if host_id not in all_hosts:
                        all_hosts[host_id] = {
                            "id": host_id,
                            "os_family": trivy_host.get("os_family", self._deployment_config.defaults.get("os_family", "Linux")),
                            "criticality_score": self._deployment_config.defaults.get("criticality_score", 0.5),
                            "subnet_id": self._deployment_config.defaults.get("subnet_id", "default"),
                            "target": target,
                        }

                    # Copy CPE mappings
                    if host_id in trivy_data.host_cpe_map:
                        host_cpe_map[host_id] = trivy_data.host_cpe_map[host_id]

            # Merge CPEs
            for cpe in trivy_data.cpes:
                if cpe["id"] not in all_cpes:
                    all_cpes[cpe["id"]] = cpe

            # Merge CVEs
            for cve in trivy_data.cves:
                if cve["id"] not in all_cves:
                    all_cves[cve["id"]] = cve

            # Merge CWEs
            for cwe in trivy_data.cwes:
                if cwe["id"] not in all_cwes:
                    all_cwes[cwe["id"]] = cwe

        # Get network edges from deployment config
        network_edges = self._deployment_config.get_network_edges()

        # If no edges defined, connect all hosts
        if not network_edges and len(all_hosts) > 1:
            host_ids = list(all_hosts.keys())
            for i, h1 in enumerate(host_ids):
                for h2 in host_ids[i + 1:]:
                    network_edges.append((h1, h2))

        return LoadedData(
            hosts=list(all_hosts.values()),
            cpes=list(all_cpes.values()),
            cves=list(all_cves.values()),
            cwes=list(all_cwes.values()),
            host_cpe_map=host_cpe_map,
            network_edges=network_edges,
        )

    def _load_trivy_source(self, source: Any) -> LoadedData:
        """Load a single Trivy source."""
        loader = TrivyDataLoader(
            source=source,
            enrich_from_nvd=self._enrich_from_nvd,
            enrich_cwe=self._enrich_cwe,
            nvd_api_key=self._nvd_api_key,
        )
        return loader.load()

    @property
    def deployment_config(self) -> DeploymentConfig:
        """Get the parsed deployment configuration."""
        return self._deployment_config

    def add_trivy_source(self, source: Any) -> None:
        """Add a Trivy source to be loaded."""
        self._trivy_sources.append(source)


def load_deployment(
    config_path: Union[str, Path],
    trivy_paths: Optional[List[Union[str, Path]]] = None,
    enrich: bool = True,
    nvd_api_key: Optional[str] = None,
) -> LoadedData:
    """Convenience function to load a deployment configuration.

    Args:
        config_path: Path to deployment YAML file.
        trivy_paths: List of paths to Trivy JSON files.
        enrich: Whether to enrich data from NVD/CWE sources.
        nvd_api_key: Optional NVD API key.

    Returns:
        LoadedData instance with merged vulnerability data.
    """
    loader = DeploymentLoader(
        deployment_config=config_path,
        trivy_sources=trivy_paths or [],
        enrich_from_nvd=enrich,
        enrich_cwe=enrich,
        nvd_api_key=nvd_api_key,
    )
    return loader.load()
