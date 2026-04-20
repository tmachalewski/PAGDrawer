"""
Graph configuration for node duplication modes.

Each node type can be grouped at different granularity levels:
- "ATTACKER" / "universal": One shared node globally
- "HOST": One node per host
- "CPE": One node per CPE (includes host context)
- "CVE": One node per CVE (includes host+CPE context)
- "CWE": One node per CWE (includes host+CPE+CVE context)
- "TI": One node per TI (most granular, includes full context)
- "singular": Legacy - maps to most granular level for that node type
"""

from dataclasses import dataclass, field
from typing import Dict, Literal

# Hierarchy of grouping levels (from least to most granular)
GROUPING_HIERARCHY = ["ATTACKER", "HOST", "CPE", "CVE", "CWE", "TI", "VC"]

# Valid grouping levels for each node type (can only group by ancestors)
VALID_GROUPINGS: Dict[str, list] = {
    "HOST": ["ATTACKER"],  # HOST is always per-attacker (universal)
    "CPE": ["ATTACKER", "HOST"],
    "CVE": ["ATTACKER", "HOST", "CPE"],
    "CWE": ["ATTACKER", "HOST", "CPE", "CVE"],
    "TI": ["ATTACKER", "HOST", "CPE", "CVE", "CWE"],
    "VC": ["ATTACKER", "HOST", "CPE", "CVE", "CWE", "TI"],
}

# For backward compatibility
DuplicationMode = Literal["universal", "singular", "ATTACKER", "HOST", "CPE", "CVE", "CWE", "TI"]


@dataclass
class GraphConfig:
    """Configuration for how the graph is built."""

    # Node duplication settings - now stores grouping level, not just singular/universal
    node_modes: Dict[str, DuplicationMode] = field(default_factory=lambda: {
        "HOST": "ATTACKER",      # Hosts are always unique anchors (universal)
        "CPE": "HOST",           # CPE per host (each host has its own software instance)
        "CVE": "CPE",            # CVE per CPE (vulnerability exists per software)
        "CWE": "CVE",            # CWE per CVE (clean linear flow)
        "TI": "CWE",             # TI per CWE (technical impact per weakness)
        "VC": "TI",              # VC per TI (state follows technical impact)
    })

    # When True, skip Layer 2 (internal network) construction.
    # INSIDE_NETWORK bridge is still created with ENTERS_NETWORK edges from
    # L1 EX:Y nodes, but no L2 hosts/CPEs/CVEs are built. Useful for
    # simpler graphs focused on external attack surface only.
    skip_layer_2: bool = False

    def _normalize_mode(self, node_type: str, mode: str) -> str:
        """Normalize legacy modes to new format."""
        if mode == "universal":
            return "ATTACKER"
        if mode == "singular":
            # Most granular = immediate predecessor
            valid = VALID_GROUPINGS.get(node_type, ["ATTACKER"])
            return valid[-1] if valid else "ATTACKER"
        return mode

    def get_grouping_level(self, node_type: str) -> str:
        """Get the grouping level for a node type."""
        mode = self.node_modes.get(node_type, "ATTACKER")
        return self._normalize_mode(node_type, mode)

    def is_singular(self, node_type: str) -> bool:
        """Check if a node type should be duplicated per parent (legacy compatibility)."""
        level = self.get_grouping_level(node_type)
        return level != "ATTACKER"

    def is_universal(self, node_type: str) -> bool:
        """Check if a node type should be shared globally (legacy compatibility)."""
        return self.get_grouping_level(node_type) == "ATTACKER"

    def should_include_context(self, node_type: str, context_type: str) -> bool:
        """
        Check if a node type's ID should include context from a parent type.

        For example, if CVE is grouped by "HOST", it should include host_id
        but not cpe_id. If grouped by "CPE", include both host_id and cpe_id.
        """
        grouping_level = self.get_grouping_level(node_type)
        if grouping_level == "ATTACKER":
            return False

        # Get the hierarchy index for grouping level and context type
        try:
            grouping_idx = GROUPING_HIERARCHY.index(grouping_level)
            context_idx = GROUPING_HIERARCHY.index(context_type)
        except ValueError:
            return False

        # Include context if it's at or before the grouping level
        return context_idx <= grouping_idx

    def set_mode(self, node_type: str, mode: DuplicationMode):
        """Set the duplication mode for a node type."""
        self.node_modes[node_type] = mode

    def to_dict(self) -> Dict[str, object]:
        """Export config as dictionary."""
        result: Dict[str, object] = dict(self.node_modes)
        result["skip_layer_2"] = self.skip_layer_2
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "GraphConfig":
        """Create config from dictionary."""
        config = cls()
        for key, value in data.items():
            if key == "skip_layer_2":
                config.skip_layer_2 = bool(value)
                continue
            # Node mode entries — accept both legacy and new formats
            if isinstance(value, str) and value in (
                "universal", "singular", "ATTACKER", "HOST", "CPE",
                "CVE", "CWE", "TI"
            ):
                config.node_modes[key] = value
        return config


# Default configuration instance
DEFAULT_CONFIG = GraphConfig()
