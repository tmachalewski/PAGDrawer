"""
Consensual Matrix for Technical Impact → Vector Changer transformation.

Based on Machalewski et al. (2024) - "Expressing Impact of Vulnerabilities"
This matrix defines how Technical Impacts from CVE descriptions map to
Vector Changer outcomes (privilege/access changes after exploitation).

The matrix was derived from expert consensus on 22 CVEs.
"""

from typing import Dict, List, Tuple
from enum import Enum


class TechnicalImpact(Enum):
    """
    Technical Impact categories from CWE Common Consequences.
    
    Based on Machalewski et al. (2024) - 24 Technical Impact categories
    as defined in the CWE framework and used in the expert study.
    """
    # Code/Command Execution
    EXECUTE_CODE = "Execute Unauthorized Code or Commands"
    
    # Privilege Escalation
    GAIN_PRIVILEGES = "Gain Privileges or Assume Identity"
    
    # Memory Operations
    MODIFY_MEMORY = "Modify Memory"
    READ_MEMORY = "Read Memory"
    
    # File/Directory Operations
    MODIFY_FILES = "Modify Files or Directories"
    READ_FILES = "Read Files or Directories"
    
    # Application Data Operations
    MODIFY_APP_DATA = "Modify Application Data"
    READ_APP_DATA = "Read Application Data"
    
    # Denial of Service variants
    DOS_CRASH = "DoS: Crash, Exit, or Restart"
    DOS_INSTABILITY = "DoS: Instability"
    DOS_CPU = "DoS: Resource Consumption (CPU)"
    DOS_MEMORY = "DoS: Resource Consumption (Memory)"
    DOS_OTHER = "DoS: Resource Consumption (Other)"
    DOS_AMPLIFICATION = "DoS: Amplification"
    
    # Security Bypass
    BYPASS_PROTECTION = "Bypass Protection Mechanism"
    HIDE_ACTIVITIES = "Hide Activities"
    
    # Quality/Reliability
    REDUCE_MAINTAINABILITY = "Reduce Maintainability"
    REDUCE_PERFORMANCE = "Reduce Performance"
    REDUCE_RELIABILITY = "Reduce Reliability"
    QUALITY_DEGRADATION = "Quality Degradation"
    
    # Logic/State
    ALTER_EXECUTION = "Alter Execution Logic"
    UNEXPECTED_STATE = "Unexpected State"
    
    # Other
    VARIES_BY_CONTEXT = "Varies by Context"
    OTHER = "Other"


# =============================================================================
# CONSENSUAL TRANSFORMATION MATRIX
# =============================================================================
# Based on Table 1 from Machalewski et al. (2024)
# "The Consensually Agreed Transformation Matrix"
#
# Maps: TechnicalImpact -> List of (VCType, VCValue) tuples gained
# VCs represent the attacker's new capabilities after exploitation

# Define privilege hierarchy (higher index = more privilege)
AV_HIERARCHY = {"N": 0, "A": 1, "L": 2, "P": 3}  # Network->Adjacent->Local->Physical
PR_HIERARCHY = {"N": 0, "L": 1, "H": 2}  # None->Low->High

CONSENSUAL_MATRIX: Dict[str, List[Tuple[str, str]]] = {
    # =========================================================================
    # HIGH IMPACT - Full system compromise (AV:L, PR:H, EX:Y)
    # =========================================================================
    
    "Execute Unauthorized Code or Commands": [
        ("AV", "L"),   # Attacker gains local access
        ("PR", "H"),   # Attacker gains high privileges
        ("EX", "Y"),   # System considered exploited
    ],
    
    "Gain Privileges or Assume Identity": [
        ("AV", "L"),   # Attacker gains local access
        ("PR", "H"),   # Attacker gains high privileges
        ("EX", "Y"),   # System considered exploited
    ],
    
    "Modify Memory": [
        ("AV", "L"),   # Attacker gains local access
        ("PR", "H"),   # Attacker gains high privileges
        ("EX", "Y"),   # System considered exploited
    ],
    
    "Modify Files or Directories": [
        ("AV", "L"),   # Attacker gains local access
        ("PR", "H"),   # Attacker gains high privileges
        ("EX", "Y"),   # System considered exploited
    ],
    
    "Modify Application Data": [
        ("AV", "L"),   # Attacker gains local access
        ("PR", "H"),   # Attacker gains high privileges
        ("EX", "Y"),   # System considered exploited
    ],
    
    # =========================================================================
    # MEDIUM IMPACT - Partial access (AV:L, PR:H without EX:Y, or just AV:L)
    # =========================================================================
    
    "Read Memory": [
        ("AV", "L"),   # Attacker gains local access
        ("PR", "H"),   # Attacker gains high privileges (can read sensitive data)
    ],
    
    "Read Application Data": [
        ("AV", "L"),   # Attacker gains local access
    ],
    
    "Read Files or Directories": [
        ("AV", "L"),   # Attacker gains local access
    ],
    
    "Bypass Protection Mechanism": [
        ("AV", "L"),   # Attacker gains local access
        ("PR", "H"),   # Attacker bypasses auth, gains high privileges
    ],
    
    # =========================================================================
    # NO PRIVILEGE GAIN - DoS and other non-escalating impacts
    # =========================================================================
    
    "DoS: Crash, Exit, or Restart": [],
    "DoS: Instability": [],
    "DoS: Resource Consumption (CPU)": [],
    "DoS: Resource Consumption (Memory)": [],
    "DoS: Resource Consumption (Other)": [],
    "DoS: Amplification": [],
    
    "Hide Activities": [],
    "Reduce Maintainability": [],
    "Reduce Performance": [],
    "Reduce Reliability": [],
    "Quality Degradation": [],
    "Alter Execution Logic": [],
    "Varies by Context": [],
    "Unexpected State": [],
    "Other": [],
    
    # =========================================================================
    # LEGACY MAPPINGS (for backward compatibility with simplified impacts)
    # =========================================================================
    
    # Simplified "Execute Unauthorized Code" (maps to full version)
    "Execute Unauthorized Code": [
        ("AV", "L"),
        ("PR", "H"),
        ("EX", "Y"),
    ],
    
    # Simplified "Gain Privileges" (maps to full version)
    "Gain Privileges": [
        ("AV", "L"),
        ("PR", "H"),
        ("EX", "Y"),
    ],
    
    # Generic "Read Data" -> maps to Read App Data
    "Read Data": [
        ("AV", "L"),
    ],
    
    # Generic "Modify Data" -> maps to Modify App Data
    "Modify Data": [
        ("AV", "L"),
        ("PR", "H"),
        ("EX", "Y"),
    ],
    
    # Generic "Denial of Service"
    "Denial of Service": [],
    
    # Generic "Bypass Protection"
    "Bypass Protection": [
        ("AV", "L"),
        ("PR", "H"),
    ],
}


# =============================================================================
# PREREQUISITE EXTRACTION FROM CVSS
# =============================================================================
# Maps CVSS components to required VC states before exploitation

def extract_prerequisites(cvss_vector: str) -> List[Tuple[str, str]]:
    """
    Extract required Vector Changer states from CVSS vector.
    
    Args:
        cvss_vector: CVSS 3.x vector string
        
    Returns:
        List of (VCType, VCValue) tuples representing required states
    """
    prereqs = []
    
    if not cvss_vector:
        return prereqs
    
    components = {}
    for part in cvss_vector.split("/"):
        if ":" in part:
            key, value = part.split(":", 1)
            components[key] = value
    
    # Attack Vector requirement
    if "AV" in components:
        prereqs.append(("AV", components["AV"]))
    
    # Privileges Required
    if "PR" in components:
        prereqs.append(("PR", components["PR"]))
    
    return prereqs


def extract_environmental_filters(cvss_vector: str) -> Dict[str, float]:
    """
    Extract environmental VCs (AC, UI) as probability modifiers.
    
    Args:
        cvss_vector: CVSS 3.x vector string
        
    Returns:
        Dict mapping filter type to probability weight
    """
    filters = {}
    
    if not cvss_vector:
        return filters
    
    components = {}
    for part in cvss_vector.split("/"):
        if ":" in part:
            key, value = part.split(":", 1)
            components[key] = value
    
    # Attack Complexity -> probability penalty
    if "AC" in components:
        # AC:H means harder, lower success probability
        filters["AC"] = 0.5 if components["AC"] == "H" else 1.0
    
    # User Interaction -> probability penalty
    if "UI" in components:
        # UI:R means user must interact, lower success probability
        filters["UI"] = 0.4 if components["UI"] == "R" else 1.0
    
    return filters


def get_post_exploitation_vcs(technical_impact: str) -> List[Tuple[str, str]]:
    """
    Get the Vector Changers gained after successful exploitation.
    
    Args:
        technical_impact: The technical impact string from CVE analysis
        
    Returns:
        List of (VCType, VCValue) tuples representing gained states
    """
    return CONSENSUAL_MATRIX.get(technical_impact, [])


# =============================================================================
# COMBINED TRANSFORMATION
# =============================================================================

def transform_cve_to_vc_edges(
    cve_id: str,
    cvss_vector: str,
    technical_impact: str
) -> Dict[str, List[Tuple[str, str]]]:
    """
    Complete transformation of CVE to VC edges.
    
    Args:
        cve_id: The CVE identifier
        cvss_vector: CVSS 3.x vector string
        technical_impact: Technical impact from NLP analysis
        
    Returns:
        Dict with 'prerequisites' and 'outcomes' lists
    """
    return {
        "prerequisites": extract_prerequisites(cvss_vector),
        "outcomes": get_post_exploitation_vcs(technical_impact),
        "filters": extract_environmental_filters(cvss_vector),
    }
