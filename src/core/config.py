"""
Graph configuration for node duplication modes.

Each node type can be:
- "universal": One shared node (e.g., one CWE-79 for all CVEs referencing it)
- "singular": Duplicated per parent (e.g., separate CWE-79 for each CVE)
"""

from dataclasses import dataclass, field
from typing import Dict, Literal

DuplicationMode = Literal["universal", "singular"]


@dataclass
class GraphConfig:
    """Configuration for how the graph is built."""
    
    # Node duplication settings
    node_modes: Dict[str, DuplicationMode] = field(default_factory=lambda: {
        "HOST": "universal",     # Hosts are always unique anchors
        "CPE": "singular",       # CPE per host (each host has its own software instance)
        "CVE": "singular",       # CVE per host (vulnerability exists on each host)
        "CWE": "singular",       # CWE per CVE (clean linear flow)
        "TI": "singular",        # TI per CWE (technical impact per weakness)
        "VC": "singular",        # VC per host (state is per-host)
    })
    
    def is_singular(self, node_type: str) -> bool:
        """Check if a node type should be duplicated per parent."""
        return self.node_modes.get(node_type, "singular") == "singular"
    
    def is_universal(self, node_type: str) -> bool:
        """Check if a node type should be shared globally."""
        return self.node_modes.get(node_type, "singular") == "universal"
    
    def set_mode(self, node_type: str, mode: DuplicationMode):
        """Set the duplication mode for a node type."""
        self.node_modes[node_type] = mode
    
    def to_dict(self) -> Dict[str, str]:
        """Export config as dictionary."""
        return dict(self.node_modes)
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "GraphConfig":
        """Create config from dictionary."""
        config = cls()
        for node_type, mode in data.items():
            if mode in ("universal", "singular"):
                config.node_modes[node_type] = mode
        return config


# Default configuration instance
DEFAULT_CONFIG = GraphConfig()
