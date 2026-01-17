"""
Pydantic schemas for deployment configuration YAML.

Allows users to define network topology, host configurations, and
mappings between Trivy scan targets and deployment hosts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class SubnetConfig(BaseModel):
    """Configuration for a network subnet."""
    model_config = {"extra": "allow"}

    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    cidr: Optional[str] = None
    zone: str = "internal"  # external, dmz, internal
    connects_to: List[str] = Field(default_factory=list)


class HostConfig(BaseModel):
    """Configuration for a single host in the deployment."""
    model_config = {"extra": "allow"}

    id: str
    name: Optional[str] = None
    os_family: str = "Linux"
    criticality_score: float = 0.5
    subnet_id: str = "default"
    trivy_targets: List[str] = Field(default_factory=list)
    """List of Trivy scan targets that map to this host.
    Can use glob patterns like 'myapp:*' or exact matches."""

    @field_validator("criticality_score")
    @classmethod
    def validate_criticality(cls, v: float) -> float:
        """Ensure criticality is between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValueError("criticality_score must be between 0 and 1")
        return v


class NetworkEdgeConfig(BaseModel):
    """Configuration for a network edge (connection)."""
    model_config = {"extra": "allow"}

    source: str
    target: str
    bidirectional: bool = True


class DeploymentConfig(BaseModel):
    """Root deployment configuration schema."""
    model_config = {"extra": "allow"}

    version: str = "1.0"
    name: Optional[str] = None
    description: Optional[str] = None

    subnets: List[SubnetConfig] = Field(default_factory=list)
    hosts: List[HostConfig] = Field(default_factory=list)
    network_edges: List[NetworkEdgeConfig] = Field(default_factory=list)

    # Default settings for hosts not explicitly configured
    defaults: Dict[str, Any] = Field(default_factory=lambda: {
        "os_family": "Linux",
        "criticality_score": 0.5,
        "subnet_id": "default",
    })

    def get_host_config(self, host_id: str) -> Optional[HostConfig]:
        """Get configuration for a specific host."""
        for host in self.hosts:
            if host.id == host_id:
                return host
        return None

    def get_subnet_config(self, subnet_id: str) -> Optional[SubnetConfig]:
        """Get configuration for a specific subnet."""
        for subnet in self.subnets:
            if subnet.id == subnet_id:
                return subnet
        return None

    def find_host_by_trivy_target(self, target: str) -> Optional[HostConfig]:
        """Find host configuration that matches a Trivy target.

        Supports exact match and glob patterns.
        """
        import fnmatch

        for host in self.hosts:
            for pattern in host.trivy_targets:
                if fnmatch.fnmatch(target, pattern) or target == pattern:
                    return host
        return None

    def get_network_edges(self) -> List[tuple[str, str]]:
        """Get all network edges as (source, target) tuples."""
        edges = []

        # From explicit edge configs
        for edge in self.network_edges:
            edges.append((edge.source, edge.target))
            if edge.bidirectional:
                edges.append((edge.target, edge.source))

        # From subnet connections
        for subnet in self.subnets:
            subnet_hosts = [h.id for h in self.hosts if h.subnet_id == subnet.id]
            for connected_subnet_id in subnet.connects_to:
                connected_hosts = [h.id for h in self.hosts if h.subnet_id == connected_subnet_id]
                # Connect all hosts in connected subnets
                for h1 in subnet_hosts:
                    for h2 in connected_hosts:
                        edges.append((h1, h2))
                        edges.append((h2, h1))

        # Remove duplicates while preserving order
        seen = set()
        unique_edges = []
        for edge in edges:
            if edge not in seen:
                seen.add(edge)
                unique_edges.append(edge)

        return unique_edges


# Example YAML configuration:
EXAMPLE_CONFIG_YAML = """
version: "1.0"
name: "Production Environment"
description: "Three-tier web application deployment"

defaults:
  os_family: Linux
  criticality_score: 0.5
  subnet_id: internal

subnets:
  - id: dmz
    name: DMZ Network
    zone: dmz
    cidr: 10.0.1.0/24
    connects_to:
      - internal

  - id: internal
    name: Internal Network
    zone: internal
    cidr: 10.0.2.0/24
    connects_to:
      - database

  - id: database
    name: Database Network
    zone: internal
    cidr: 10.0.3.0/24

hosts:
  - id: web-server-1
    name: Web Server 1
    os_family: Linux
    criticality_score: 0.7
    subnet_id: dmz
    trivy_targets:
      - "nginx:*"
      - "frontend:*"

  - id: api-server-1
    name: API Server 1
    os_family: Linux
    criticality_score: 0.8
    subnet_id: internal
    trivy_targets:
      - "api:*"
      - "backend:*"

  - id: db-server-1
    name: Database Server
    os_family: Linux
    criticality_score: 1.0
    subnet_id: database
    trivy_targets:
      - "postgres:*"
      - "mysql:*"

network_edges:
  # Additional direct connections beyond subnet topology
  - source: web-server-1
    target: api-server-1
    bidirectional: true
"""
