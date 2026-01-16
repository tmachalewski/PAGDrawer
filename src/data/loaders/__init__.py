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

__all__ = [
    "DataLoader",
    "LoadedData",
    "DataLoadError",
    "DataValidationError",
    "MockDataLoader",
    "CWEFetcher",
    "get_technical_impact",
    "get_technical_impacts",
    "STATIC_CWE_MAPPING",
    "SEVERITY_TO_IMPACT",
]
