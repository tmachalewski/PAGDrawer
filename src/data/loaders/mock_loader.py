"""
Mock data loader for development and testing.

Wraps the existing mock_data.py to conform to the DataLoader interface.
"""

from typing import List, Tuple

from .base import DataLoader, LoadedData
from ..mock_data import (
    MOCK_HOSTS,
    MOCK_CPES,
    MOCK_CVES,
    MOCK_CWES,
    MOCK_HOST_CPE_MAP,
    MOCK_NETWORK_EDGES,
)


class MockDataLoader(DataLoader):
    """Data loader that uses built-in mock data for testing and development."""

    def load(self) -> LoadedData:
        """Load mock data from the mock_data module.

        Returns:
            LoadedData instance containing mock vulnerability data.
        """
        # Convert network edges to proper tuple format
        network_edges: List[Tuple[str, str]] = [
            (src, dst) for src, dst in MOCK_NETWORK_EDGES
        ]

        return LoadedData(
            hosts=MOCK_HOSTS.copy(),
            cpes=MOCK_CPES.copy(),
            cves=MOCK_CVES.copy(),
            cwes=MOCK_CWES.copy(),
            host_cpe_map={k: v.copy() for k, v in MOCK_HOST_CPE_MAP.items()},
            network_edges=network_edges,
        )

    def validate_source(self) -> bool:
        """Mock data is always available.

        Returns:
            Always True since mock data is built-in.
        """
        return True
