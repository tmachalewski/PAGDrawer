"""
Data loaders for PAGDrawer.

Provides abstract base class and implementations for loading vulnerability
data from various sources (mock data, Trivy, NVD, etc.).
"""

from .base import DataLoader, LoadedData, DataLoadError, DataValidationError
from .mock_loader import MockDataLoader

__all__ = [
    "DataLoader",
    "LoadedData",
    "DataLoadError",
    "DataValidationError",
    "MockDataLoader",
]
