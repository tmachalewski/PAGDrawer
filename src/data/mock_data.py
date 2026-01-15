"""
Mock data for PoC development.

Contains sample CVEs, CPEs, CWEs, and EPSS scores for testing graph construction.
"""

from typing import List, Dict, Any

# =============================================================================
# SAMPLE CWEs (Abstract Weakness Categories)
# =============================================================================

MOCK_CWES: List[Dict[str, Any]] = [
    {
        "id": "CWE-79",
        "name": "Cross-site Scripting (XSS)",
        "description": "Improper neutralization of input during web page generation allowing script injection."
    },
    {
        "id": "CWE-89",
        "name": "SQL Injection",
        "description": "Improper neutralization of special elements used in SQL commands."
    },
    {
        "id": "CWE-119",
        "name": "Buffer Overflow",
        "description": "Improper restriction of operations within the bounds of a memory buffer."
    },
    {
        "id": "CWE-20",
        "name": "Improper Input Validation",
        "description": "The product does not validate or incorrectly validates input."
    },
    {
        "id": "CWE-78",
        "name": "OS Command Injection",
        "description": "Improper neutralization of special elements used in an OS command."
    },
    {
        "id": "CWE-287",
        "name": "Improper Authentication",
        "description": "The actor claims to have a given identity but does not prove it."
    },
    {
        "id": "CWE-22",
        "name": "Path Traversal",
        "description": "Improper limitation of a pathname to a restricted directory."
    },
    {
        "id": "CWE-352",
        "name": "Cross-Site Request Forgery (CSRF)",
        "description": "The web application does not verify that the request was intentionally submitted."
    },
]


# =============================================================================
# SAMPLE CPEs (Software Products)
# =============================================================================

MOCK_CPES: List[Dict[str, Any]] = [
    # Web Servers
    {"id": "cpe:2.3:a:apache:http_server:2.4.41:*", "vendor": "apache", "product": "http_server", "version": "2.4.41"},
    {"id": "cpe:2.3:a:apache:http_server:2.4.49:*", "vendor": "apache", "product": "http_server", "version": "2.4.49"},
    {"id": "cpe:2.3:a:nginx:nginx:1.18.0:*", "vendor": "nginx", "product": "nginx", "version": "1.18.0"},
    
    # Databases
    {"id": "cpe:2.3:a:mysql:mysql:5.7.32:*", "vendor": "mysql", "product": "mysql", "version": "5.7.32"},
    {"id": "cpe:2.3:a:postgresql:postgresql:12.5:*", "vendor": "postgresql", "product": "postgresql", "version": "12.5"},
    
    # Programming Runtimes
    {"id": "cpe:2.3:a:oracle:jdk:11.0.9:*", "vendor": "oracle", "product": "jdk", "version": "11.0.9"},
    {"id": "cpe:2.3:a:python:python:3.8.5:*", "vendor": "python", "product": "python", "version": "3.8.5"},
    
    # Application Frameworks
    {"id": "cpe:2.3:a:apache:struts:2.5.22:*", "vendor": "apache", "product": "struts", "version": "2.5.22"},
    {"id": "cpe:2.3:a:apache:log4j:2.14.1:*", "vendor": "apache", "product": "log4j", "version": "2.14.1"},
    
    # Operating Systems Components
    {"id": "cpe:2.3:a:openssh:openssh:7.9:*", "vendor": "openssh", "product": "openssh", "version": "7.9"},
    {"id": "cpe:2.3:a:openssl:openssl:1.1.1g:*", "vendor": "openssl", "product": "openssl", "version": "1.1.1g"},
]


# =============================================================================
# SAMPLE CVEs (Vulnerabilities)
# Designed for multi-stage attack chains:
#   Stage 1: Remote Initial Access (AV:N, PR:N) → gains (AV:L, PR:L)
#   Stage 2: Local Privilege Escalation (AV:L, PR:L) → gains (PR:H)
# =============================================================================

MOCK_CVES: List[Dict[str, Any]] = [
    # =========================================================================
    # STAGE 1: INITIAL ACCESS CVEs (Remote → Local)
    # Prereq: AV:N, PR:N (network access, no privileges)
    # Outcome: AV:L, PR:L (local access, low privileges)
    # =========================================================================
    
    # Log4Shell - Classic RCE
    {
        "id": "CVE-2021-44228",
        "description": "Apache Log4j2 RCE via JNDI - remote attacker gains shell access.",
        "epss_score": 0.975,
        "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
        "cpe_id": "cpe:2.3:a:apache:log4j:2.14.1:*",
        "cwe_id": "CWE-78",
        "technical_impact": "Execute Unauthorized Code"  # → AV:L, PR:L, EX:Y
    },
    
    # Apache Path Traversal RCE
    {
        "id": "CVE-2021-41773",
        "description": "Path traversal and RCE in Apache HTTP Server 2.4.49.",
        "epss_score": 0.943,
        "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        "cpe_id": "cpe:2.3:a:apache:http_server:2.4.49:*",
        "cwe_id": "CWE-22",
        "technical_impact": "Execute Unauthorized Code"  # → AV:L, PR:L, EX:Y
    },
    
    # WordPress File Upload RCE
    {
        "id": "CVE-2020-25213",
        "description": "WordPress File Manager plugin allows arbitrary file upload for RCE.",
        "epss_score": 0.567,
        "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        "cpe_id": "cpe:2.3:a:nginx:nginx:1.18.0:*",
        "cwe_id": "CWE-20",
        "technical_impact": "Execute Unauthorized Code"  # → AV:L, PR:L, EX:Y
    },
    
    # Struts OGNL Injection RCE
    {
        "id": "CVE-2017-5638",
        "description": "Apache Struts OGNL injection allows remote code execution.",
        "epss_score": 0.887,
        "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        "cpe_id": "cpe:2.3:a:apache:struts:2.5.22:*",
        "cwe_id": "CWE-78",
        "technical_impact": "Execute Unauthorized Code"  # → AV:L, PR:L, EX:Y
    },
    
    # JDK Deserialization RCE
    {
        "id": "CVE-2018-2628",
        "description": "Oracle WebLogic Java deserialization leads to RCE.",
        "epss_score": 0.856,
        "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        "cpe_id": "cpe:2.3:a:oracle:jdk:11.0.9:*",
        "cwe_id": "CWE-78",
        "technical_impact": "Execute Unauthorized Code"  # → AV:L, PR:L, EX:Y
    },
    
    # =========================================================================
    # STAGE 2: PRIVILEGE ESCALATION CVEs (Local Low → Local High)
    # Prereq: AV:L, PR:L (local access, low privileges)
    # Outcome: PR:H (high/root privileges)
    # =========================================================================
    
    # Sudo Baron Samedit - Local Privesc
    {
        "id": "CVE-2021-3156",
        "description": "Sudo heap-based buffer overflow for root privilege escalation.",
        "epss_score": 0.823,
        "cvss_vector": "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H",
        "cpe_id": "cpe:2.3:a:openssh:openssh:7.9:*",  # On same hosts as SSH
        "cwe_id": "CWE-119",
        "technical_impact": "Gain Privileges"  # → PR:H, EX:Y
    },
    
    # Linux Netfilter Privesc
    {
        "id": "CVE-2021-22555",
        "description": "Linux Netfilter heap OOB write for privilege escalation.",
        "epss_score": 0.678,
        "cvss_vector": "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H",
        "cpe_id": "cpe:2.3:a:python:python:3.8.5:*",  # Python hosts
        "cwe_id": "CWE-119",
        "technical_impact": "Gain Privileges"  # → PR:H, EX:Y
    },
    
    # Polkit Privesc
    {
        "id": "CVE-2021-4034",
        "description": "Polkit pkexec local privilege escalation (PwnKit).",
        "epss_score": 0.892,
        "cvss_vector": "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H",
        "cpe_id": "cpe:2.3:a:apache:http_server:2.4.41:*",  # Apache 2.4.41 hosts
        "cwe_id": "CWE-119",
        "technical_impact": "Gain Privileges"  # → PR:H, EX:Y
    },
    
    # Dirty Pipe - Kernel Privesc
    {
        "id": "CVE-2022-0847",
        "description": "Linux kernel pipe buffer flags allow arbitrary file overwrite.",
        "epss_score": 0.867,
        "cvss_vector": "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H",
        "cpe_id": "cpe:2.3:a:postgresql:postgresql:12.5:*",  # DB hosts
        "cwe_id": "CWE-119",
        "technical_impact": "Gain Privileges"  # → PR:H, EX:Y
    },
    
    # Windows Print Spooler Privesc
    {
        "id": "CVE-2021-34527",
        "description": "PrintNightmare - Windows Print Spooler remote code execution and privesc.",
        "epss_score": 0.912,
        "cvss_vector": "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H",
        "cpe_id": "cpe:2.3:a:mysql:mysql:5.7.32:*",  # DB hosts with MySQL
        "cwe_id": "CWE-78",
        "technical_impact": "Gain Privileges"  # → PR:H, EX:Y
    },
    
    # =========================================================================
    # NON-CHAINABLE CVEs (for contrast)
    # These don't enable further attacks
    # =========================================================================
    
    # Read Data - No privesc
    {
        "id": "CVE-2020-35489",
        "description": "SQL injection vulnerability allowing database read access.",
        "epss_score": 0.721,
        "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N",
        "cpe_id": "cpe:2.3:a:mysql:mysql:5.7.32:*",
        "cwe_id": "CWE-89",
        "technical_impact": "Read Data"  # → No VC gain (info disclosure only)
    },
    
    # XSS - Requires user interaction
    {
        "id": "CVE-2019-11358",
        "description": "jQuery XSS vulnerability in HTML parsing.",
        "epss_score": 0.412,
        "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N",
        "cpe_id": "cpe:2.3:a:apache:struts:2.5.22:*",
        "cwe_id": "CWE-79",
        "technical_impact": "Execute Unauthorized Code"  # → AV:L, PR:L but UI:R penalty
    },
]



# =============================================================================
# SAMPLE HOST CONFIGURATIONS
# =============================================================================

MOCK_HOSTS: List[Dict[str, Any]] = [
    {"id": "host-001", "os_family": "Linux", "criticality_score": 0.9, "subnet_id": "dmz"},
    {"id": "host-002", "os_family": "Linux", "criticality_score": 0.7, "subnet_id": "dmz"},
    {"id": "host-003", "os_family": "Windows", "criticality_score": 0.5, "subnet_id": "internal"},
    {"id": "host-004", "os_family": "Linux", "criticality_score": 0.8, "subnet_id": "internal"},
    {"id": "host-005", "os_family": "Windows", "criticality_score": 1.0, "subnet_id": "db"},
    {"id": "host-006", "os_family": "Linux", "criticality_score": 0.6, "subnet_id": "db"},
]


# =============================================================================
# HOST-CPE ASSIGNMENTS (Which software runs on which host)
# =============================================================================

MOCK_HOST_CPE_MAP: Dict[str, List[str]] = {
    "host-001": [
        "cpe:2.3:a:apache:http_server:2.4.49:*",
        "cpe:2.3:a:apache:log4j:2.14.1:*",
        "cpe:2.3:a:openssh:openssh:7.9:*",
    ],
    "host-002": [
        "cpe:2.3:a:nginx:nginx:1.18.0:*",
        "cpe:2.3:a:python:python:3.8.5:*",
        "cpe:2.3:a:openssh:openssh:7.9:*",
    ],
    "host-003": [
        "cpe:2.3:a:apache:struts:2.5.22:*",
        "cpe:2.3:a:oracle:jdk:11.0.9:*",
    ],
    "host-004": [
        "cpe:2.3:a:apache:http_server:2.4.41:*",
        "cpe:2.3:a:openssl:openssl:1.1.1g:*",
        "cpe:2.3:a:python:python:3.8.5:*",
    ],
    "host-005": [
        "cpe:2.3:a:mysql:mysql:5.7.32:*",
        "cpe:2.3:a:oracle:jdk:11.0.9:*",
    ],
    "host-006": [
        "cpe:2.3:a:postgresql:postgresql:12.5:*",
        "cpe:2.3:a:openssh:openssh:7.9:*",
    ],
}


# =============================================================================
# NETWORK TOPOLOGY (Host connectivity)
# =============================================================================

MOCK_NETWORK_EDGES: List[tuple] = [
    # DMZ hosts connected to each other
    ("host-001", "host-002"),
    # DMZ can reach internal
    ("host-001", "host-003"),
    ("host-002", "host-004"),
    # Internal hosts connected
    ("host-003", "host-004"),
    # Internal can reach DB
    ("host-003", "host-005"),
    ("host-004", "host-005"),
    ("host-004", "host-006"),
    # DB hosts connected
    ("host-005", "host-006"),
]
