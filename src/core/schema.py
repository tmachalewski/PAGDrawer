"""
Schema definitions for the Heterogeneous Knowledge Graph.

Defines the 5-Node Schema and 6-Edge Schema as per the thesis methodology.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List
import numpy as np


# =============================================================================
# NODE TYPES
# =============================================================================

class NodeType(Enum):
    """The 6 distinct node types in the knowledge graph."""
    HOST = auto()      # Infrastructure root - physical/virtual asset
    CPE = auto()       # Attack surface - specific software instance
    CVE = auto()       # The exploit - specific flaw
    CWE = auto()       # Semantic anchor - abstract weakness
    TI = auto()        # Technical Impact - consequence of exploitation
    VC = auto()        # Vector Changer - state required/gained


# =============================================================================
# EDGE TYPES
# =============================================================================

class EdgeType(Enum):
    """Edge types defining relationships between nodes."""
    # Static edges
    RUNS = auto()              # Host -> CPE (software stack)
    HAS_VULN = auto()          # CPE -> CVE (defect link)
    IS_INSTANCE_OF = auto()    # CVE -> CWE (semantic clustering)
    CONNECTED_TO = auto()      # Host -> Host (network reachability)
    HAS_IMPACT = auto()        # CWE -> TI (technical impact)
    
    # Dynamic state machine edges
    ALLOWS_EXPLOIT = auto()    # VC -> CVE (pre-condition)
    YIELDS_STATE = auto()      # CVE -> VC (post-condition)


# =============================================================================
# VECTOR CHANGER TYPES
# =============================================================================

class VCType(Enum):
    """Vector Changer categories from CVSS decomposition."""
    # Group A: State Mutators (change topology)
    AV = "AttackVector"        # Network, Adjacent, Local, Physical
    PR = "PrivilegesRequired"  # None, Low, High
    EX = "Exploited"           # Final compromise state
    
    # Group B: Static Filters (change probability)
    AC = "AttackComplexity"    # Low, High
    UI = "UserInteraction"     # None, Required


class AVValue(Enum):
    """Attack Vector values."""
    NETWORK = "N"
    ADJACENT = "A"
    LOCAL = "L"
    PHYSICAL = "P"


class PRValue(Enum):
    """Privileges Required values."""
    NONE = "N"
    LOW = "L"
    HIGH = "H"


class ACValue(Enum):
    """Attack Complexity values."""
    LOW = "L"
    HIGH = "H"


class UIValue(Enum):
    """User Interaction values."""
    NONE = "N"
    REQUIRED = "R"


# =============================================================================
# NODE DATA CLASSES
# =============================================================================

@dataclass
class HostNode:
    """Infrastructure root node representing a physical or virtual asset."""
    id: str
    os_family: str  # Linux, Windows, macOS
    criticality_score: float  # 0.0 - 1.0
    subnet_id: str  # Defines network reachability
    
    node_type: NodeType = field(default=NodeType.HOST, init=False)


@dataclass
class CPENode:
    """Attack surface node representing a specific software instance."""
    id: str  # Full CPE URI (e.g., cpe:2.3:a:apache:http_server:2.4.41:*)
    vendor: str
    product: str
    version: str
    edition: Optional[str] = None
    
    node_type: NodeType = field(default=NodeType.CPE, init=False)


@dataclass
class CVENode:
    """Exploit node representing a specific vulnerability."""
    id: str  # CVE ID (e.g., CVE-2021-44228)
    description: str
    epss_score: float  # Exploit Prediction Scoring System (0.0 - 1.0)
    cvss_vector: str  # CVSS vector string
    embedding: Optional[np.ndarray] = None  # S-BERT embedding (768-dim)
    
    node_type: NodeType = field(default=NodeType.CVE, init=False)


@dataclass
class CWENode:
    """Semantic anchor node representing an abstract weakness."""
    id: str  # CWE ID (e.g., CWE-79)
    name: str
    description: str
    embedding: Optional[np.ndarray] = None  # S-BERT embedding
    
    node_type: NodeType = field(default=NodeType.CWE, init=False)


@dataclass
class VCNode:
    """Vector Changer node representing attacker state."""
    id: str  # e.g., "VC:AV:N" or "VC:PR:H"
    vc_type: VCType
    value: str  # The specific value (e.g., "N" for Network)
    probability_weight: float = 1.0  # For Group B filters
    
    node_type: NodeType = field(default=NodeType.VC, init=False)


# =============================================================================
# EDGE DATA CLASSES
# =============================================================================

@dataclass
class Edge:
    """Generic edge connecting two nodes."""
    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0  # Optional weight for probabilistic edges


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_vc_id(vc_type: VCType, value: str) -> str:
    """Create a standardized VC node ID."""
    return f"VC:{vc_type.name}:{value}"


def parse_cvss_vector(vector_string: str) -> dict:
    """
    Parse a CVSS 3.x vector string into components.
    
    Example: "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    """
    if not vector_string:
        return {}
    
    components = {}
    parts = vector_string.split("/")
    
    for part in parts:
        if ":" in part:
            key, value = part.split(":", 1)
            components[key] = value
    
    return components
