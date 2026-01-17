"""
Data loaders for PAGDrawer.

Provides abstract base class and implementations for loading vulnerability
data from various sources (mock data, Trivy, NVD, etc.).
"""

from .base import DataLoader, LoadedData, DataLoadError, DataValidationError
from .mock_loader import MockDataLoader
from .cwe_fetcher import (
    CWEFetcher,
    get_technical_impact,
    get_technical_impacts,
    STATIC_CWE_MAPPING,
    SEVERITY_TO_IMPACT,
)
from .nvd_fetcher import (
    NVDFetcher,
    fetch_cve,
    fetch_epss,
    enrich_cve,
)
from .trivy_loader import TrivyDataLoader, load_trivy_json

__all__ = [
    # Base classes
    "DataLoader",
    "LoadedData",
    "DataLoadError",
    "DataValidationError",
    # Mock data
    "MockDataLoader",
    # CWE fetcher
    "CWEFetcher",
    "get_technical_impact",
    "get_technical_impacts",
    "STATIC_CWE_MAPPING",
    "SEVERITY_TO_IMPACT",
    # NVD fetcher
    "NVDFetcher",
    "fetch_cve",
    "fetch_epss",
    "enrich_cve",
    # Trivy loader
    "TrivyDataLoader",
    "load_trivy_json",
]
