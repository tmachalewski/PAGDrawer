"""
CWE Data Fetcher - Retrieves CWE information from the CWE REST API.

Uses the official MITRE CWE REST API (https://cwe-api.mitre.org/api/v1/)
to extract "Common Consequences" from CWE entries and map them to
Technical Impact values for the consensual matrix transformation.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from src.data.mongo_client import (
    COLLECTION_CWE_IMPACTS,
    TTL_CWE_DAYS,
    cached_doc_if_fresh,
    upsert_cached_doc,
    get_db,
)

logger = logging.getLogger(__name__)

# CWE REST API base URL
CWE_API_BASE_URL = "https://cwe-api.mitre.org/api/v1"


# =============================================================================
# STATIC CWE → TECHNICAL IMPACT MAPPING
# =============================================================================
# Pre-defined mapping for common CWEs based on their Common Consequences.
# This provides fast lookups without needing to fetch from the API.

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
    3. REST API from cwe-api.mitre.org for missing CWEs
    """

    def __init__(self, timeout: int = 30, force_refresh: bool = False):
        """
        Initialize the CWE fetcher.

        Args:
            timeout: Request timeout in seconds for API calls
            force_refresh: When True, bypass the Mongo cache on every call
        """
        self.timeout = timeout
        self.force_refresh = force_refresh

    def _get_cached(self, cwe_id: str) -> Optional[Dict[str, Any]]:
        """Return the full cached document for a CWE or None if stale/absent."""
        return cached_doc_if_fresh(
            COLLECTION_CWE_IMPACTS, cwe_id, TTL_CWE_DAYS, self.force_refresh
        )

    def _upsert_impacts(self, cwe_id: str, impacts: List[str], source: str = "rest") -> None:
        """Persist the impact list for a CWE, preserving any cached full info."""
        existing = get_db()[COLLECTION_CWE_IMPACTS].find_one({"_id": cwe_id}) or {}
        payload = {
            "technical_impacts": impacts,
            "source": source,
        }
        # Preserve info fields if previously cached
        for field in ("name", "description"):
            if field in existing:
                payload[field] = existing[field]
        upsert_cached_doc(COLLECTION_CWE_IMPACTS, cwe_id, payload)

    def _upsert_info(self, cwe_id: str, info: Dict[str, Any]) -> None:
        """Persist the full info dict (name, description, impacts) for a CWE."""
        payload = {
            "name": info.get("name", ""),
            "description": info.get("description", ""),
            "technical_impacts": info.get("technical_impacts", []),
            "source": "rest",
        }
        upsert_cached_doc(COLLECTION_CWE_IMPACTS, cwe_id, payload)

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
            fetch_if_missing: Whether to fetch from API if not in cache/static

        Returns:
            List of Technical Impact strings.
        """
        # Normalize CWE ID
        cwe_id = self._normalize_cwe_id(cwe_id)

        # Try static mapping first (fastest; in-memory, no network/DB)
        if cwe_id in STATIC_CWE_MAPPING:
            return STATIC_CWE_MAPPING[cwe_id]

        # Try Mongo cache
        cached = self._get_cached(cwe_id)
        if cached is not None and cached.get("technical_impacts"):
            return cached["technical_impacts"]

        # Try fetching from API
        if fetch_if_missing:
            impacts = self._fetch_from_api(cwe_id)
            if impacts:
                self._upsert_impacts(cwe_id, impacts, source="rest")
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
            fetch_if_missing: Whether to fetch from API if not in cache

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

    def _get_numeric_id(self, cwe_id: str) -> Optional[str]:
        """Extract numeric ID from CWE ID string."""
        match = re.match(r"CWE-(\d+)", cwe_id)
        return match.group(1) if match else None

    def _fetch_from_api(self, cwe_id: str) -> Optional[List[str]]:
        """
        Fetch CWE data from the REST API.

        Args:
            cwe_id: Normalized CWE ID (e.g., "CWE-78")

        Returns:
            List of Technical Impact strings, or None if not found.
        """
        numeric_id = self._get_numeric_id(cwe_id)
        if not numeric_id:
            return None

        url = f"{CWE_API_BASE_URL}/cwe/weakness/{numeric_id}"

        try:
            request = Request(url, headers={"Accept": "application/json"})
            with urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))

            # API response structure: {"Weaknesses": [{...weakness data...}]}
            weakness = self._extract_weakness_from_response(data)
            if not weakness:
                return None

            # Extract Common Consequences from the weakness
            impacts = self._extract_consequences_from_json(weakness)

            if impacts:
                logger.info(f"Fetched {len(impacts)} impacts for {cwe_id} from API")

            return impacts if impacts else None

        except HTTPError as e:
            if e.code == 404:
                logger.debug(f"CWE {cwe_id} not found in API (404)")
            else:
                logger.warning(f"HTTP error fetching {cwe_id}: {e.code} {e.reason}")
            return None
        except URLError as e:
            logger.warning(f"URL error fetching {cwe_id}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error for {cwe_id}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error fetching {cwe_id}: {e}")
            return None

    def _extract_weakness_from_response(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract the weakness object from API response.

        The API returns: {"Weaknesses": [{...weakness data...}]}

        Args:
            data: Raw API response

        Returns:
            The weakness dictionary, or None if not found.
        """
        weaknesses = data.get("Weaknesses", [])
        if isinstance(weaknesses, list) and weaknesses:
            return weaknesses[0]
        return None

    def _extract_consequences_from_json(self, data: Dict[str, Any]) -> List[str]:
        """
        Extract Technical Impact values from API JSON response.

        Args:
            data: Weakness data from CWE API

        Returns:
            List of Technical Impact strings.
        """
        impacts: Set[str] = set()

        # API uses "CommonConsequences" (camelCase, no underscore)
        # Structure: {"CommonConsequences": [{"Scope": [...], "Impact": [...], "Note": "..."}, ...]}
        consequences = data.get("CommonConsequences", [])

        # Handle both single consequence (dict) and multiple (list)
        if isinstance(consequences, dict):
            consequences = [consequences]

        for consequence in consequences:
            # Impact can be a string or list of strings
            impact_data = consequence.get("Impact", [])

            if isinstance(impact_data, str):
                impact_data = [impact_data]

            for impact in impact_data:
                if impact:
                    normalized = self._normalize_impact(impact.strip())
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
            # Skip if a fresh doc already exists
            if self._get_cached(cwe_id) is not None:
                continue
            self._upsert_impacts(cwe_id, impacts, source="static")
            count += 1

        if count > 0:
            logger.info(f"Preloaded {count} CWEs into Mongo cache")

        return count

    def get_cwe_info(self, cwe_id: str, fetch_if_missing: bool = True) -> Optional[Dict]:
        """
        Get full CWE information including name and description.

        Args:
            cwe_id: CWE identifier
            fetch_if_missing: Whether to fetch from API if not in cache

        Returns:
            Dict with id, name, description, and technical_impacts.
        """
        cwe_id = self._normalize_cwe_id(cwe_id)

        # Check Mongo cache first — return stored info if we have name/description
        cached = self._get_cached(cwe_id)
        if cached is not None and cached.get("name"):
            return {
                "id": cwe_id,
                "name": cached.get("name", ""),
                "description": cached.get("description", ""),
                "technical_impacts": cached.get("technical_impacts", []),
            }

        if not fetch_if_missing:
            return None

        # Fetch from API
        numeric_id = self._get_numeric_id(cwe_id)
        if not numeric_id:
            return None

        url = f"{CWE_API_BASE_URL}/cwe/weakness/{numeric_id}"

        try:
            request = Request(url, headers={"Accept": "application/json"})
            with urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))

            # Extract weakness from response wrapper
            weakness = self._extract_weakness_from_response(data)
            if not weakness:
                return None

            name = weakness.get("Name", "Unknown")
            description = weakness.get("Description", "")

            # Also extract ExtendedDescription if available
            extended = weakness.get("ExtendedDescription", "")
            if extended and not description:
                description = extended

            impacts = self._extract_consequences_from_json(weakness)

            info = {
                "id": cwe_id,
                "name": name,
                "description": description,
                "technical_impacts": impacts,
            }

            # Cache the info in Mongo
            self._upsert_info(cwe_id, info)

            return info

        except HTTPError as e:
            if e.code == 404:
                logger.debug(f"CWE {cwe_id} not found in API (404)")
            else:
                logger.warning(f"HTTP error fetching info for {cwe_id}: {e.code}")
            return None
        except Exception as e:
            logger.warning(f"Error fetching CWE info for {cwe_id}: {e}")
            return None

    def fetch_multiple(self, cwe_ids: List[str]) -> Dict[str, List[str]]:
        """
        Fetch multiple CWEs.

        Note: The batch API endpoint (/cwe/74,79) only returns minimal data,
        so we fetch each CWE individually to get full details including
        CommonConsequences.

        Args:
            cwe_ids: List of CWE identifiers

        Returns:
            Dict mapping CWE IDs to their Technical Impacts.
        """
        results: Dict[str, List[str]] = {}

        # Separate CWEs into cached and uncached
        uncached_ids = []
        for cwe_id in cwe_ids:
            normalized = self._normalize_cwe_id(cwe_id)
            if normalized in STATIC_CWE_MAPPING:
                results[normalized] = STATIC_CWE_MAPPING[normalized]
                continue
            cached = self._get_cached(normalized)
            if cached is not None and cached.get("technical_impacts"):
                results[normalized] = cached["technical_impacts"]
            else:
                uncached_ids.append(normalized)

        if not uncached_ids:
            return results

        # Fetch each uncached CWE individually
        # (batch endpoint doesn't include CommonConsequences)
        fetched_count = 0
        for cwe_id in uncached_ids:
            impacts = self._fetch_from_api(cwe_id)
            if impacts:
                results[cwe_id] = impacts
                fetched_count += 1

        if fetched_count > 0:
            logger.info(f"Fetched {fetched_count} CWEs from API")

        return results

    def clear_cache(self):
        """Delete all cached CWE documents from MongoDB."""
        get_db()[COLLECTION_CWE_IMPACTS].delete_many({})
        logger.info("CWE cache cleared (Mongo)")


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
        fetch_if_missing: Whether to fetch from API if not in cache

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
        fetch_if_missing: Whether to fetch from API if not in cache

    Returns:
        List of Technical Impact strings.
    """
    return get_fetcher().get_technical_impacts(cwe_id, severity, fetch_if_missing)
