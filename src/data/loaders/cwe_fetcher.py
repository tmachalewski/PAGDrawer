"""
CWE Data Fetcher - Retrieves CWE information from cwe.mitre.org.

Extracts "Common Consequences" from CWE entries to map CWE IDs to
Technical Impact values for the consensual matrix transformation.
"""

import json
import logging
import re
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.request import urlopen
from urllib.error import URLError

logger = logging.getLogger(__name__)

# Cache directory for CWE data
CACHE_DIR = Path(__file__).parent.parent / "cache"
CWE_CACHE_FILE = CACHE_DIR / "cwe_cache.json"

# CWE XML download URL (Research Concepts view - most complete)
CWE_XML_URL = "https://cwe.mitre.org/data/xml/cwec_latest.xml.zip"

# XML namespace used in CWE data
CWE_NS = {"cwe": "http://cwe.mitre.org/cwe-7"}


# =============================================================================
# STATIC CWE → TECHNICAL IMPACT MAPPING
# =============================================================================
# Pre-defined mapping for common CWEs based on their Common Consequences.
# This provides fast lookups without needing to fetch from the web.

STATIC_CWE_MAPPING: Dict[str, List[str]] = {
    # Injection vulnerabilities
    "CWE-78": ["Execute Unauthorized Code or Commands", "Read Files or Directories",
               "Modify Files or Directories", "Hide Activities"],
    "CWE-77": ["Execute Unauthorized Code or Commands"],
    "CWE-89": ["Execute Unauthorized Code or Commands", "Read Application Data",
               "Modify Application Data", "Gain Privileges or Assume Identity",
               "Bypass Protection Mechanism"],
    "CWE-90": ["Gain Privileges or Assume Identity", "Bypass Protection Mechanism",
               "Read Application Data"],
    "CWE-91": ["Read Application Data", "Modify Application Data"],
    "CWE-94": ["Execute Unauthorized Code or Commands"],
    "CWE-95": ["Execute Unauthorized Code or Commands"],
    "CWE-96": ["Execute Unauthorized Code or Commands"],

    # XSS variants
    "CWE-79": ["Execute Unauthorized Code or Commands", "Bypass Protection Mechanism",
               "Read Application Data"],
    "CWE-80": ["Execute Unauthorized Code or Commands"],

    # Path Traversal / File Access
    "CWE-22": ["Read Files or Directories", "Modify Files or Directories",
               "Execute Unauthorized Code or Commands"],
    "CWE-23": ["Read Files or Directories"],
    "CWE-36": ["Read Files or Directories", "Modify Files or Directories"],
    "CWE-73": ["Read Files or Directories", "Modify Files or Directories"],
    "CWE-434": ["Execute Unauthorized Code or Commands"],

    # Buffer/Memory vulnerabilities
    "CWE-119": ["Execute Unauthorized Code or Commands", "Modify Memory",
                "Read Memory", "DoS: Crash, Exit, or Restart"],
    "CWE-120": ["Execute Unauthorized Code or Commands", "Modify Memory"],
    "CWE-121": ["Execute Unauthorized Code or Commands", "Modify Memory"],
    "CWE-122": ["Execute Unauthorized Code or Commands", "Modify Memory"],
    "CWE-125": ["Read Memory", "DoS: Crash, Exit, or Restart"],
    "CWE-787": ["Execute Unauthorized Code or Commands", "Modify Memory",
                "DoS: Crash, Exit, or Restart"],
    "CWE-416": ["Execute Unauthorized Code or Commands", "DoS: Crash, Exit, or Restart"],
    "CWE-415": ["Execute Unauthorized Code or Commands", "DoS: Crash, Exit, or Restart"],
    "CWE-476": ["DoS: Crash, Exit, or Restart"],

    # Authentication/Authorization
    "CWE-287": ["Gain Privileges or Assume Identity", "Bypass Protection Mechanism"],
    "CWE-306": ["Gain Privileges or Assume Identity", "Bypass Protection Mechanism"],
    "CWE-862": ["Gain Privileges or Assume Identity", "Read Application Data",
                "Modify Application Data"],
    "CWE-863": ["Gain Privileges or Assume Identity"],
    "CWE-284": ["Gain Privileges or Assume Identity", "Bypass Protection Mechanism"],
    "CWE-285": ["Gain Privileges or Assume Identity"],
    "CWE-269": ["Gain Privileges or Assume Identity"],
    "CWE-250": ["Gain Privileges or Assume Identity"],

    # Cryptographic issues
    "CWE-327": ["Bypass Protection Mechanism", "Read Application Data"],
    "CWE-328": ["Bypass Protection Mechanism"],
    "CWE-326": ["Bypass Protection Mechanism", "Read Application Data"],
    "CWE-295": ["Bypass Protection Mechanism", "Gain Privileges or Assume Identity"],
    "CWE-311": ["Read Application Data"],
    "CWE-312": ["Read Application Data"],
    "CWE-319": ["Read Application Data"],
    "CWE-320": ["Bypass Protection Mechanism"],

    # DoS vulnerabilities
    "CWE-400": ["DoS: Resource Consumption (Other)"],
    "CWE-770": ["DoS: Resource Consumption (Memory)"],
    "CWE-835": ["DoS: Resource Consumption (CPU)"],
    "CWE-674": ["DoS: Crash, Exit, or Restart", "DoS: Resource Consumption (CPU)"],
    "CWE-834": ["DoS: Resource Consumption (CPU)"],
    "CWE-399": ["DoS: Resource Consumption (Other)"],
    "CWE-404": ["DoS: Resource Consumption (Other)"],

    # Deserialization
    "CWE-502": ["Execute Unauthorized Code or Commands", "Gain Privileges or Assume Identity"],

    # Information Disclosure
    "CWE-200": ["Read Application Data"],
    "CWE-209": ["Read Application Data"],
    "CWE-532": ["Read Application Data"],
    "CWE-538": ["Read Files or Directories"],
    "CWE-497": ["Read Application Data"],

    # Input Validation
    "CWE-20": ["Varies by Context"],
    "CWE-74": ["Execute Unauthorized Code or Commands", "Modify Application Data"],
    "CWE-116": ["Execute Unauthorized Code or Commands"],

    # Race Conditions
    "CWE-362": ["Gain Privileges or Assume Identity", "Modify Application Data",
                "DoS: Crash, Exit, or Restart"],
    "CWE-367": ["Gain Privileges or Assume Identity", "Bypass Protection Mechanism"],

    # Integer issues
    "CWE-190": ["Execute Unauthorized Code or Commands", "DoS: Crash, Exit, or Restart"],
    "CWE-191": ["Execute Unauthorized Code or Commands", "DoS: Crash, Exit, or Restart"],
    "CWE-369": ["DoS: Crash, Exit, or Restart"],

    # Use After Free / Double Free
    "CWE-416": ["Execute Unauthorized Code or Commands", "DoS: Crash, Exit, or Restart"],
    "CWE-415": ["Execute Unauthorized Code or Commands", "DoS: Crash, Exit, or Restart"],

    # Format String
    "CWE-134": ["Execute Unauthorized Code or Commands", "Read Memory", "DoS: Crash, Exit, or Restart"],

    # SSRF
    "CWE-918": ["Bypass Protection Mechanism", "Read Application Data"],

    # XXE
    "CWE-611": ["Read Files or Directories", "DoS: Resource Consumption (Other)"],

    # CSRF
    "CWE-352": ["Gain Privileges or Assume Identity", "Modify Application Data"],

    # Open Redirect
    "CWE-601": ["Gain Privileges or Assume Identity"],

    # Hardcoded Credentials
    "CWE-798": ["Gain Privileges or Assume Identity", "Bypass Protection Mechanism"],
    "CWE-259": ["Gain Privileges or Assume Identity"],

    # Session Management
    "CWE-384": ["Gain Privileges or Assume Identity"],
    "CWE-613": ["Gain Privileges or Assume Identity"],

    # Improper Error Handling
    "CWE-754": ["DoS: Crash, Exit, or Restart"],
    "CWE-755": ["DoS: Crash, Exit, or Restart", "Unexpected State"],

    # NULL Pointer
    "CWE-476": ["DoS: Crash, Exit, or Restart"],

    # Missing Encryption
    "CWE-311": ["Read Application Data"],
    "CWE-319": ["Read Application Data"],
}


# =============================================================================
# SEVERITY-BASED FALLBACK MAPPING
# =============================================================================
# Used when CWE is not in the static mapping and cannot be fetched

SEVERITY_TO_IMPACT: Dict[str, str] = {
    "CRITICAL": "Execute Unauthorized Code or Commands",
    "HIGH": "Gain Privileges or Assume Identity",
    "MEDIUM": "Bypass Protection Mechanism",
    "LOW": "Read Application Data",
    "UNKNOWN": "Other",
}


class CWEFetcher:
    """
    Fetches and caches CWE data for Technical Impact mapping.

    Uses a combination of:
    1. Static pre-defined mapping for common CWEs
    2. Local cache for previously fetched CWEs
    3. XML download from cwe.mitre.org for missing CWEs
    """

    def __init__(self, cache_file: Optional[Path] = None):
        """
        Initialize the CWE fetcher.

        Args:
            cache_file: Optional path to cache file. Defaults to src/data/cache/cwe_cache.json
        """
        self.cache_file = cache_file or CWE_CACHE_FILE
        self._cache: Dict[str, List[str]] = {}
        self._xml_data: Optional[ET.Element] = None
        self._load_cache()

    def _load_cache(self):
        """Load cached CWE mappings from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r") as f:
                    self._cache = json.load(f)
                logger.info(f"Loaded {len(self._cache)} cached CWE mappings")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load CWE cache: {e}")
                self._cache = {}

    def _save_cache(self):
        """Save CWE mappings to disk cache."""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self._cache, f, indent=2)
            logger.debug(f"Saved {len(self._cache)} CWE mappings to cache")
        except IOError as e:
            logger.warning(f"Failed to save CWE cache: {e}")

    def get_technical_impacts(
        self,
        cwe_id: str,
        severity: Optional[str] = None,
        fetch_if_missing: bool = True
    ) -> List[str]:
        """
        Get Technical Impact values for a CWE.

        Args:
            cwe_id: CWE identifier (e.g., "CWE-78" or "78")
            severity: Optional CVSS severity for fallback (CRITICAL, HIGH, MEDIUM, LOW)
            fetch_if_missing: Whether to fetch from web if not in cache/static

        Returns:
            List of Technical Impact strings.
        """
        # Normalize CWE ID
        cwe_id = self._normalize_cwe_id(cwe_id)

        # Try static mapping first (fastest)
        if cwe_id in STATIC_CWE_MAPPING:
            return STATIC_CWE_MAPPING[cwe_id]

        # Try cache
        if cwe_id in self._cache:
            return self._cache[cwe_id]

        # Try fetching from XML
        if fetch_if_missing:
            impacts = self._fetch_from_xml(cwe_id)
            if impacts:
                self._cache[cwe_id] = impacts
                self._save_cache()
                return impacts

        # Fallback to severity-based mapping
        if severity:
            severity_upper = severity.upper()
            if severity_upper in SEVERITY_TO_IMPACT:
                return [SEVERITY_TO_IMPACT[severity_upper]]

        # Ultimate fallback
        return ["Other"]

    def get_primary_impact(
        self,
        cwe_id: str,
        severity: Optional[str] = None,
        fetch_if_missing: bool = True
    ) -> str:
        """
        Get the primary (first) Technical Impact for a CWE.

        This is useful when only one impact is needed for graph building.

        Args:
            cwe_id: CWE identifier
            severity: Optional CVSS severity for fallback
            fetch_if_missing: Whether to fetch from web if not in cache

        Returns:
            Primary Technical Impact string.
        """
        impacts = self.get_technical_impacts(cwe_id, severity, fetch_if_missing)
        return impacts[0] if impacts else "Other"

    def _normalize_cwe_id(self, cwe_id: str) -> str:
        """Normalize CWE ID to 'CWE-XXX' format."""
        cwe_id = str(cwe_id).strip().upper()

        # Handle numeric-only input
        if cwe_id.isdigit():
            return f"CWE-{cwe_id}"

        # Handle 'CWE-XXX' format
        if cwe_id.startswith("CWE-"):
            return cwe_id

        # Handle 'CWEXXXX' format (no hyphen)
        match = re.match(r"CWE(\d+)", cwe_id)
        if match:
            return f"CWE-{match.group(1)}"

        # Return as-is if can't normalize
        return cwe_id

    def _fetch_from_xml(self, cwe_id: str) -> Optional[List[str]]:
        """
        Fetch CWE data from downloaded XML.

        Args:
            cwe_id: Normalized CWE ID (e.g., "CWE-78")

        Returns:
            List of Technical Impact strings, or None if not found.
        """
        # Load XML data if not already loaded
        if self._xml_data is None:
            self._xml_data = self._download_cwe_xml()
            if self._xml_data is None:
                return None

        # Extract numeric ID
        match = re.match(r"CWE-(\d+)", cwe_id)
        if not match:
            return None
        numeric_id = match.group(1)

        # Find the weakness element
        weakness = self._xml_data.find(
            f".//cwe:Weakness[@ID='{numeric_id}']",
            CWE_NS
        )

        if weakness is None:
            logger.debug(f"CWE {cwe_id} not found in XML data")
            return None

        # Extract Common Consequences
        impacts = self._extract_consequences(weakness)

        if impacts:
            logger.info(f"Fetched {len(impacts)} impacts for {cwe_id}")

        return impacts if impacts else None

    def _download_cwe_xml(self) -> Optional[ET.Element]:
        """
        Download and parse the CWE XML data.

        Returns:
            Parsed XML root element, or None on failure.
        """
        logger.info(f"Downloading CWE XML from {CWE_XML_URL}...")

        try:
            with urlopen(CWE_XML_URL, timeout=60) as response:
                zip_data = BytesIO(response.read())

            # Extract XML from ZIP
            with zipfile.ZipFile(zip_data) as zf:
                # Find the XML file in the archive
                xml_files = [n for n in zf.namelist() if n.endswith(".xml")]
                if not xml_files:
                    logger.error("No XML file found in CWE ZIP archive")
                    return None

                xml_content = zf.read(xml_files[0])

            # Parse XML
            root = ET.fromstring(xml_content)
            logger.info("Successfully downloaded and parsed CWE XML")
            return root

        except URLError as e:
            logger.error(f"Failed to download CWE XML: {e}")
            return None
        except ET.ParseError as e:
            logger.error(f"Failed to parse CWE XML: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading CWE XML: {e}")
            return None

    def _extract_consequences(self, weakness: ET.Element) -> List[str]:
        """
        Extract Technical Impact values from a Weakness element.

        Args:
            weakness: XML Element for a CWE Weakness

        Returns:
            List of Technical Impact strings.
        """
        impacts: Set[str] = set()

        # Find Common_Consequences element
        consequences = weakness.find("cwe:Common_Consequences", CWE_NS)
        if consequences is None:
            return []

        # Extract each Consequence
        for consequence in consequences.findall("cwe:Consequence", CWE_NS):
            # Get Impact element(s)
            for impact in consequence.findall("cwe:Impact", CWE_NS):
                impact_text = impact.text
                if impact_text:
                    # Normalize the impact text
                    normalized = self._normalize_impact(impact_text.strip())
                    if normalized:
                        impacts.add(normalized)

        return list(impacts)

    def _normalize_impact(self, impact: str) -> Optional[str]:
        """
        Normalize Technical Impact text to match our TechnicalImpact enum.

        Args:
            impact: Raw impact text from CWE

        Returns:
            Normalized impact string, or None if not mappable.
        """
        # Direct mapping for exact matches
        known_impacts = {
            "Execute Unauthorized Code or Commands",
            "Gain Privileges or Assume Identity",
            "Modify Memory",
            "Read Memory",
            "Modify Files or Directories",
            "Read Files or Directories",
            "Modify Application Data",
            "Read Application Data",
            "DoS: Crash, Exit, or Restart",
            "DoS: Instability",
            "DoS: Resource Consumption (CPU)",
            "DoS: Resource Consumption (Memory)",
            "DoS: Resource Consumption (Other)",
            "DoS: Amplification",
            "Bypass Protection Mechanism",
            "Hide Activities",
            "Reduce Maintainability",
            "Reduce Performance",
            "Reduce Reliability",
            "Quality Degradation",
            "Alter Execution Logic",
            "Unexpected State",
            "Varies by Context",
            "Other",
        }

        if impact in known_impacts:
            return impact

        # Handle common variations
        impact_lower = impact.lower()

        if "execute" in impact_lower and "code" in impact_lower:
            return "Execute Unauthorized Code or Commands"
        if "privilege" in impact_lower or "assume identity" in impact_lower:
            return "Gain Privileges or Assume Identity"
        if "denial of service" in impact_lower or "dos" in impact_lower:
            if "crash" in impact_lower:
                return "DoS: Crash, Exit, or Restart"
            if "cpu" in impact_lower:
                return "DoS: Resource Consumption (CPU)"
            if "memory" in impact_lower:
                return "DoS: Resource Consumption (Memory)"
            return "DoS: Resource Consumption (Other)"
        if "bypass" in impact_lower:
            return "Bypass Protection Mechanism"
        if "read" in impact_lower:
            if "file" in impact_lower:
                return "Read Files or Directories"
            if "memory" in impact_lower:
                return "Read Memory"
            return "Read Application Data"
        if "modify" in impact_lower or "write" in impact_lower:
            if "file" in impact_lower:
                return "Modify Files or Directories"
            if "memory" in impact_lower:
                return "Modify Memory"
            return "Modify Application Data"
        if "hide" in impact_lower:
            return "Hide Activities"

        # Log unmapped impacts for debugging
        logger.debug(f"Unmapped impact: {impact}")
        return None

    def preload_common_cwes(self) -> int:
        """
        Preload common CWEs into cache.

        This copies the static mapping into the cache for persistence.

        Returns:
            Number of CWEs loaded.
        """
        count = 0
        for cwe_id, impacts in STATIC_CWE_MAPPING.items():
            if cwe_id not in self._cache:
                self._cache[cwe_id] = impacts
                count += 1

        if count > 0:
            self._save_cache()
            logger.info(f"Preloaded {count} CWEs into cache")

        return count

    def get_cwe_info(self, cwe_id: str) -> Optional[Dict]:
        """
        Get full CWE information including name and description.

        Args:
            cwe_id: CWE identifier

        Returns:
            Dict with id, name, description, and technical_impacts.
        """
        cwe_id = self._normalize_cwe_id(cwe_id)

        # Load XML if needed
        if self._xml_data is None:
            self._xml_data = self._download_cwe_xml()
            if self._xml_data is None:
                return None

        # Extract numeric ID
        match = re.match(r"CWE-(\d+)", cwe_id)
        if not match:
            return None
        numeric_id = match.group(1)

        # Find the weakness element
        weakness = self._xml_data.find(
            f".//cwe:Weakness[@ID='{numeric_id}']",
            CWE_NS
        )

        if weakness is None:
            return None

        name = weakness.get("Name", "Unknown")

        # Get description
        description_elem = weakness.find("cwe:Description", CWE_NS)
        description = description_elem.text if description_elem is not None else ""

        # Get impacts
        impacts = self._extract_consequences(weakness)

        return {
            "id": cwe_id,
            "name": name,
            "description": description,
            "technical_impacts": impacts,
        }

    def clear_cache(self):
        """Clear the local cache."""
        self._cache = {}
        if self.cache_file.exists():
            self.cache_file.unlink()
        logger.info("CWE cache cleared")


# =============================================================================
# MODULE-LEVEL CONVENIENCE FUNCTIONS
# =============================================================================

_default_fetcher: Optional[CWEFetcher] = None


def get_fetcher() -> CWEFetcher:
    """Get or create the default CWE fetcher instance."""
    global _default_fetcher
    if _default_fetcher is None:
        _default_fetcher = CWEFetcher()
    return _default_fetcher


def get_technical_impact(
    cwe_id: str,
    severity: Optional[str] = None,
    fetch_if_missing: bool = True
) -> str:
    """
    Get the primary Technical Impact for a CWE.

    Convenience function using the default fetcher.

    Args:
        cwe_id: CWE identifier (e.g., "CWE-78" or "78")
        severity: Optional CVSS severity for fallback
        fetch_if_missing: Whether to fetch from web if not in cache

    Returns:
        Primary Technical Impact string.
    """
    return get_fetcher().get_primary_impact(cwe_id, severity, fetch_if_missing)


def get_technical_impacts(
    cwe_id: str,
    severity: Optional[str] = None,
    fetch_if_missing: bool = True
) -> List[str]:
    """
    Get all Technical Impacts for a CWE.

    Convenience function using the default fetcher.

    Args:
        cwe_id: CWE identifier
        severity: Optional CVSS severity for fallback
        fetch_if_missing: Whether to fetch from web if not in cache

    Returns:
        List of Technical Impact strings.
    """
    return get_fetcher().get_technical_impacts(cwe_id, severity, fetch_if_missing)
