"""
NVD Data Fetcher - Retrieves CVE information from NIST NVD and EPSS from FIRST.

Fetches vulnerability data including:
- CVSS vectors and scores
- CWE mappings
- EPSS (Exploit Prediction Scoring System) scores
- CVE descriptions
"""

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# Cache directory
CACHE_DIR = Path(__file__).parent.parent / "cache"
NVD_CACHE_FILE = CACHE_DIR / "nvd_cache.json"
EPSS_CACHE_FILE = CACHE_DIR / "epss_cache.json"

# API endpoints
NVD_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
EPSS_API_URL = "https://api.first.org/data/v1/epss"

# Rate limiting settings
# NVD: ~5 requests per 30 seconds without API key
# FIRST EPSS: No documented limits, but be respectful
NVD_REQUEST_DELAY = 6.0  # seconds between requests (conservative)
EPSS_REQUEST_DELAY = 0.5  # seconds between requests

# Cache TTL (time-to-live)
CACHE_TTL_DAYS = 7  # Re-fetch after 7 days


class NVDFetcher:
    """
    Fetches CVE data from NVD and EPSS scores from FIRST.

    Features:
    - Fetches CVSS vectors, CWE mappings, descriptions
    - Fetches EPSS scores for exploit probability
    - Local caching with TTL
    - Rate limiting to respect API limits
    """

    def __init__(
        self,
        nvd_cache_file: Optional[Path] = None,
        epss_cache_file: Optional[Path] = None,
        nvd_api_key: Optional[str] = None,
    ):
        """
        Initialize the NVD fetcher.

        Args:
            nvd_cache_file: Path to NVD cache file
            epss_cache_file: Path to EPSS cache file
            nvd_api_key: Optional NVD API key for higher rate limits
        """
        self.nvd_cache_file = nvd_cache_file or NVD_CACHE_FILE
        self.epss_cache_file = epss_cache_file or EPSS_CACHE_FILE
        self.nvd_api_key = nvd_api_key

        self._nvd_cache: Dict[str, Dict] = {}
        self._epss_cache: Dict[str, Dict] = {}
        self._last_nvd_request: float = 0
        self._last_epss_request: float = 0

        self._load_caches()

    def _load_caches(self):
        """Load cached data from disk."""
        # Load NVD cache
        if self.nvd_cache_file.exists():
            try:
                with open(self.nvd_cache_file, "r") as f:
                    self._nvd_cache = json.load(f)
                logger.info(f"Loaded {len(self._nvd_cache)} cached NVD entries")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load NVD cache: {e}")
                self._nvd_cache = {}

        # Load EPSS cache
        if self.epss_cache_file.exists():
            try:
                with open(self.epss_cache_file, "r") as f:
                    self._epss_cache = json.load(f)
                logger.info(f"Loaded {len(self._epss_cache)} cached EPSS entries")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load EPSS cache: {e}")
                self._epss_cache = {}

    def _save_nvd_cache(self):
        """Save NVD cache to disk."""
        self.nvd_cache_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.nvd_cache_file, "w") as f:
                json.dump(self._nvd_cache, f, indent=2)
        except IOError as e:
            logger.warning(f"Failed to save NVD cache: {e}")

    def _save_epss_cache(self):
        """Save EPSS cache to disk."""
        self.epss_cache_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.epss_cache_file, "w") as f:
                json.dump(self._epss_cache, f, indent=2)
        except IOError as e:
            logger.warning(f"Failed to save EPSS cache: {e}")

    def _is_cache_valid(self, cached_entry: Dict) -> bool:
        """Check if a cached entry is still valid based on TTL."""
        if "cached_at" not in cached_entry:
            return False

        cached_at = datetime.fromisoformat(cached_entry["cached_at"])
        expires_at = cached_at + timedelta(days=CACHE_TTL_DAYS)
        return datetime.now() < expires_at

    def _rate_limit_nvd(self):
        """Apply rate limiting for NVD requests."""
        elapsed = time.time() - self._last_nvd_request
        if elapsed < NVD_REQUEST_DELAY:
            sleep_time = NVD_REQUEST_DELAY - elapsed
            logger.debug(f"Rate limiting NVD: sleeping {sleep_time:.1f}s")
            time.sleep(sleep_time)
        self._last_nvd_request = time.time()

    def _rate_limit_epss(self):
        """Apply rate limiting for EPSS requests."""
        elapsed = time.time() - self._last_epss_request
        if elapsed < EPSS_REQUEST_DELAY:
            sleep_time = EPSS_REQUEST_DELAY - elapsed
            time.sleep(sleep_time)
        self._last_epss_request = time.time()

    def fetch_cve(
        self,
        cve_id: str,
        use_cache: bool = True,
        fetch_epss: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch CVE data from NVD.

        Args:
            cve_id: CVE identifier (e.g., "CVE-2021-44228")
            use_cache: Whether to use cached data
            fetch_epss: Whether to also fetch EPSS score

        Returns:
            Dict with CVE data including:
            - id: CVE ID
            - description: Vulnerability description
            - cvss_vector: CVSS v3.1 vector string
            - cvss_score: CVSS base score
            - severity: CVSS severity (CRITICAL, HIGH, etc.)
            - cwe_ids: List of associated CWE IDs
            - epss_score: EPSS score (if fetch_epss=True)
            - published: Publication date
            - modified: Last modification date
        """
        cve_id = cve_id.upper()

        # Check cache first
        if use_cache and cve_id in self._nvd_cache:
            cached = self._nvd_cache[cve_id]
            if self._is_cache_valid(cached):
                logger.debug(f"Using cached data for {cve_id}")
                # Optionally refresh EPSS
                if fetch_epss and "epss_score" not in cached:
                    epss = self.fetch_epss(cve_id)
                    if epss is not None:
                        cached["epss_score"] = epss
                        self._save_nvd_cache()
                return cached

        # Fetch from NVD API
        self._rate_limit_nvd()
        cve_data = self._fetch_from_nvd(cve_id)

        if cve_data is None:
            return None

        # Fetch EPSS score
        if fetch_epss:
            epss = self.fetch_epss(cve_id, use_cache=use_cache)
            if epss is not None:
                cve_data["epss_score"] = epss

        # Cache the result
        cve_data["cached_at"] = datetime.now().isoformat()
        self._nvd_cache[cve_id] = cve_data
        self._save_nvd_cache()

        return cve_data

    def _fetch_from_nvd(self, cve_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch CVE data directly from NVD API.

        Args:
            cve_id: CVE identifier

        Returns:
            Parsed CVE data or None on failure.
        """
        url = f"{NVD_API_URL}?cveId={cve_id}"

        headers = {"Accept": "application/json"}
        if self.nvd_api_key:
            headers["apiKey"] = self.nvd_api_key

        logger.info(f"Fetching {cve_id} from NVD API...")

        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))

            vulnerabilities = data.get("vulnerabilities", [])
            if not vulnerabilities:
                logger.warning(f"CVE {cve_id} not found in NVD")
                return None

            cve_item = vulnerabilities[0].get("cve", {})
            return self._parse_cve_item(cve_item)

        except HTTPError as e:
            if e.code == 404:
                logger.warning(f"CVE {cve_id} not found (404)")
            elif e.code == 403:
                logger.error("NVD API rate limit exceeded (403)")
            else:
                logger.error(f"NVD API error: {e.code} {e.reason}")
            return None
        except URLError as e:
            logger.error(f"Failed to connect to NVD API: {e}")
            return None
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse NVD response: {e}")
            return None

    def _parse_cve_item(self, cve_item: Dict) -> Dict[str, Any]:
        """
        Parse a CVE item from NVD API response.

        Args:
            cve_item: Raw CVE object from API

        Returns:
            Normalized CVE data dict.
        """
        cve_id = cve_item.get("id", "")

        # Get description (prefer English)
        description = ""
        for desc in cve_item.get("descriptions", []):
            if desc.get("lang") == "en":
                description = desc.get("value", "")
                break
        if not description:
            descriptions = cve_item.get("descriptions", [])
            if descriptions:
                description = descriptions[0].get("value", "")

        # Get CVSS v3.1 metrics (preferred) or v3.0
        cvss_vector = ""
        cvss_score = 0.0
        severity = "UNKNOWN"

        metrics = cve_item.get("metrics", {})

        # Try CVSS v3.1 first
        cvss_v31 = metrics.get("cvssMetricV31", [])
        if cvss_v31:
            primary = cvss_v31[0]
            cvss_data = primary.get("cvssData", {})
            cvss_vector = cvss_data.get("vectorString", "")
            cvss_score = cvss_data.get("baseScore", 0.0)
            severity = cvss_data.get("baseSeverity", "UNKNOWN")

        # Fall back to CVSS v3.0
        if not cvss_vector:
            cvss_v30 = metrics.get("cvssMetricV30", [])
            if cvss_v30:
                primary = cvss_v30[0]
                cvss_data = primary.get("cvssData", {})
                cvss_vector = cvss_data.get("vectorString", "")
                cvss_score = cvss_data.get("baseScore", 0.0)
                severity = cvss_data.get("baseSeverity", "UNKNOWN")

        # Fall back to CVSS v2
        if not cvss_vector:
            cvss_v2 = metrics.get("cvssMetricV2", [])
            if cvss_v2:
                primary = cvss_v2[0]
                cvss_data = primary.get("cvssData", {})
                cvss_vector = cvss_data.get("vectorString", "")
                cvss_score = cvss_data.get("baseScore", 0.0)
                severity = primary.get("baseSeverity", "UNKNOWN")

        # Get CWE IDs
        cwe_ids = []
        for weakness in cve_item.get("weaknesses", []):
            for desc in weakness.get("description", []):
                cwe_value = desc.get("value", "")
                if cwe_value.startswith("CWE-"):
                    cwe_ids.append(cwe_value)
                elif cwe_value.startswith("NVD-CWE"):
                    # NVD-CWE-noinfo or NVD-CWE-Other - skip these
                    pass

        # Get dates
        published = cve_item.get("published", "")
        modified = cve_item.get("lastModified", "")

        # Get references (first 5)
        references = []
        for ref in cve_item.get("references", [])[:5]:
            references.append({
                "url": ref.get("url", ""),
                "source": ref.get("source", ""),
            })

        return {
            "id": cve_id,
            "description": description,
            "cvss_vector": cvss_vector,
            "cvss_score": cvss_score,
            "severity": severity,
            "cwe_ids": cwe_ids,
            "published": published,
            "modified": modified,
            "references": references,
        }

    def fetch_epss(
        self,
        cve_id: str,
        use_cache: bool = True
    ) -> Optional[float]:
        """
        Fetch EPSS score from FIRST API.

        Args:
            cve_id: CVE identifier
            use_cache: Whether to use cached data

        Returns:
            EPSS score (0.0-1.0) or None if not found.
        """
        cve_id = cve_id.upper()

        # Check cache
        if use_cache and cve_id in self._epss_cache:
            cached = self._epss_cache[cve_id]
            if self._is_cache_valid(cached):
                return cached.get("epss_score")

        # Fetch from FIRST API
        self._rate_limit_epss()

        url = f"{EPSS_API_URL}?cve={cve_id}"

        logger.debug(f"Fetching EPSS for {cve_id}...")

        try:
            with urlopen(url, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8"))

            epss_data = data.get("data", [])
            if not epss_data:
                logger.debug(f"No EPSS data for {cve_id}")
                return None

            epss_score = float(epss_data[0].get("epss", 0))

            # Cache the result
            self._epss_cache[cve_id] = {
                "epss_score": epss_score,
                "cached_at": datetime.now().isoformat(),
            }
            self._save_epss_cache()

            return epss_score

        except (URLError, json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to fetch EPSS for {cve_id}: {e}")
            return None

    def fetch_multiple_cves(
        self,
        cve_ids: List[str],
        use_cache: bool = True,
        fetch_epss: bool = True
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fetch data for multiple CVEs.

        Args:
            cve_ids: List of CVE identifiers
            use_cache: Whether to use cached data
            fetch_epss: Whether to also fetch EPSS scores

        Returns:
            Dict mapping CVE ID to CVE data.
        """
        results = {}

        # First, batch fetch EPSS scores (more efficient)
        if fetch_epss:
            self._batch_fetch_epss(cve_ids, use_cache)

        # Then fetch individual CVEs from NVD
        for cve_id in cve_ids:
            data = self.fetch_cve(cve_id, use_cache=use_cache, fetch_epss=False)
            if data:
                # Add EPSS from cache
                if cve_id.upper() in self._epss_cache:
                    data["epss_score"] = self._epss_cache[cve_id.upper()].get("epss_score")
                results[cve_id] = data

        return results

    def _batch_fetch_epss(self, cve_ids: List[str], use_cache: bool = True):
        """
        Batch fetch EPSS scores for multiple CVEs.

        FIRST API supports comma-separated CVE IDs for batch requests.
        """
        # Filter out cached CVEs
        if use_cache:
            cve_ids = [
                cve for cve in cve_ids
                if cve.upper() not in self._epss_cache
                or not self._is_cache_valid(self._epss_cache[cve.upper()])
            ]

        if not cve_ids:
            return

        # FIRST API allows multiple CVEs (up to reasonable limit)
        # Process in batches of 30
        batch_size = 30
        for i in range(0, len(cve_ids), batch_size):
            batch = cve_ids[i:i + batch_size]
            cve_param = ",".join(batch)

            self._rate_limit_epss()

            url = f"{EPSS_API_URL}?cve={cve_param}"

            try:
                with urlopen(url, timeout=30) as response:
                    data = json.loads(response.read().decode("utf-8"))

                for item in data.get("data", []):
                    cve_id = item.get("cve", "").upper()
                    epss_score = float(item.get("epss", 0))

                    self._epss_cache[cve_id] = {
                        "epss_score": epss_score,
                        "cached_at": datetime.now().isoformat(),
                    }

                logger.info(f"Batch fetched EPSS for {len(batch)} CVEs")

            except (URLError, json.JSONDecodeError) as e:
                logger.warning(f"Failed to batch fetch EPSS: {e}")

        self._save_epss_cache()

    def enrich_cve_data(
        self,
        cve_data: Dict[str, Any],
        fetch_if_missing: bool = True
    ) -> Dict[str, Any]:
        """
        Enrich existing CVE data with NVD information.

        Fills in missing fields from NVD if available.

        Args:
            cve_data: Existing CVE data dict with at least 'id'
            fetch_if_missing: Whether to fetch from NVD if data is missing

        Returns:
            Enriched CVE data dict.
        """
        cve_id = cve_data.get("id", "")
        if not cve_id:
            return cve_data

        # Get NVD data
        nvd_data = None
        if fetch_if_missing:
            nvd_data = self.fetch_cve(cve_id, fetch_epss=True)
        elif cve_id.upper() in self._nvd_cache:
            nvd_data = self._nvd_cache[cve_id.upper()]

        if not nvd_data:
            return cve_data

        # Fill in missing fields
        enriched = cve_data.copy()

        if not enriched.get("description"):
            enriched["description"] = nvd_data.get("description", "")

        if not enriched.get("cvss_vector"):
            enriched["cvss_vector"] = nvd_data.get("cvss_vector", "")

        if not enriched.get("epss_score") and "epss_score" in nvd_data:
            enriched["epss_score"] = nvd_data["epss_score"]

        if not enriched.get("cwe_ids") and nvd_data.get("cwe_ids"):
            enriched["cwe_ids"] = nvd_data["cwe_ids"]

        if not enriched.get("severity"):
            enriched["severity"] = nvd_data.get("severity", "UNKNOWN")

        return enriched

    def clear_cache(self):
        """Clear all cached data."""
        self._nvd_cache = {}
        self._epss_cache = {}

        if self.nvd_cache_file.exists():
            self.nvd_cache_file.unlink()
        if self.epss_cache_file.exists():
            self.epss_cache_file.unlink()

        logger.info("NVD/EPSS caches cleared")

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "nvd_entries": len(self._nvd_cache),
            "epss_entries": len(self._epss_cache),
        }


# =============================================================================
# MODULE-LEVEL CONVENIENCE FUNCTIONS
# =============================================================================

_default_fetcher: Optional[NVDFetcher] = None


def get_fetcher() -> NVDFetcher:
    """Get or create the default NVD fetcher instance."""
    global _default_fetcher
    if _default_fetcher is None:
        _default_fetcher = NVDFetcher()
    return _default_fetcher


def fetch_cve(cve_id: str, fetch_epss: bool = True) -> Optional[Dict[str, Any]]:
    """
    Fetch CVE data from NVD.

    Convenience function using the default fetcher.

    Args:
        cve_id: CVE identifier
        fetch_epss: Whether to also fetch EPSS score

    Returns:
        CVE data dict or None if not found.
    """
    return get_fetcher().fetch_cve(cve_id, fetch_epss=fetch_epss)


def fetch_epss(cve_id: str) -> Optional[float]:
    """
    Fetch EPSS score for a CVE.

    Convenience function using the default fetcher.

    Args:
        cve_id: CVE identifier

    Returns:
        EPSS score (0.0-1.0) or None.
    """
    return get_fetcher().fetch_epss(cve_id)


def enrich_cve(cve_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enrich CVE data with NVD information.

    Convenience function using the default fetcher.

    Args:
        cve_data: Existing CVE data with 'id' field

    Returns:
        Enriched CVE data.
    """
    return get_fetcher().enrich_cve_data(cve_data)
