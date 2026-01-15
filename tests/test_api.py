"""
Tests for src/viz/app.py - FastAPI endpoints.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from contextlib import asynccontextmanager

# Need to initialize the app before importing
from src.graph.builder import build_knowledge_graph
from src.core.config import GraphConfig
import src.viz.app as app_module

# Initialize graph before tests
app_module.graph_builder = build_knowledge_graph(GraphConfig())
from src.viz.app import app


@pytest.fixture
async def async_client():
    """Create async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestGraphEndpoint:
    """Tests for GET /api/graph endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_graph_returns_200(self, async_client):
        """Should return 200 OK."""
        response = await async_client.get("/api/graph")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_get_graph_returns_json(self, async_client):
        """Should return JSON response."""
        response = await async_client.get("/api/graph")
        data = response.json()
        assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_get_graph_cytoscape_format(self, async_client):
        """Should return Cytoscape.js format."""
        response = await async_client.get("/api/graph")
        data = response.json()
        
        assert "elements" in data
        assert "nodes" in data["elements"]
        assert "edges" in data["elements"]
    
    @pytest.mark.asyncio
    async def test_nodes_have_data(self, async_client):
        """Nodes should have data property."""
        response = await async_client.get("/api/graph")
        data = response.json()
        
        nodes = data["elements"]["nodes"]
        assert len(nodes) > 0
        
        for node in nodes[:5]:  # Check first 5
            assert "data" in node
            assert "id" in node["data"]
            assert "type" in node["data"]
    
    @pytest.mark.asyncio
    async def test_edges_have_data(self, async_client):
        """Edges should have source and target."""
        response = await async_client.get("/api/graph")
        data = response.json()
        
        edges = data["elements"]["edges"]
        assert len(edges) > 0
        
        for edge in edges[:5]:  # Check first 5
            assert "data" in edge
            assert "source" in edge["data"]
            assert "target" in edge["data"]


class TestStatsEndpoint:
    """Tests for GET /api/stats endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_stats_returns_200(self, async_client):
        """Should return 200 OK."""
        response = await async_client.get("/api/stats")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_get_stats_format(self, async_client):
        """Should return expected format."""
        response = await async_client.get("/api/stats")
        data = response.json()
        
        assert "total_nodes" in data
        assert "total_edges" in data
        assert "node_counts" in data
        assert "edge_counts" in data
    
    @pytest.mark.asyncio
    async def test_stats_have_positive_counts(self, async_client):
        """Stats should show positive counts."""
        response = await async_client.get("/api/stats")
        data = response.json()
        
        assert data["total_nodes"] > 0
        assert data["total_edges"] > 0


class TestConfigEndpoint:
    """Tests for /api/config endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_config_returns_200(self, async_client):
        """GET should return 200 OK."""
        response = await async_client.get("/api/config")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_get_config_format(self, async_client):
        """Should return node mode configuration."""
        response = await async_client.get("/api/config")
        data = response.json()
        
        assert "HOST" in data
        assert "CPE" in data
        assert "TI" in data
        assert data["HOST"] == "universal"
    
    @pytest.mark.asyncio
    async def test_post_config_updates(self, async_client):
        """POST should update configuration."""
        new_config = {
            "HOST": "universal",
            "CPE": "universal",  # Change to universal
            "CVE": "singular",
            "CWE": "singular",
            "TI": "singular",
            "VC": "singular"
        }
        
        response = await async_client.post("/api/config", json=new_config)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ok"
        assert "stats" in data
    
    @pytest.mark.asyncio
    async def test_post_config_rebuilds_graph(self, async_client):
        """POST should rebuild graph with new config."""
        new_config = {
            "HOST": "universal",
            "CPE": "singular",
            "CVE": "singular",
            "CWE": "singular",
            "TI": "singular",
            "VC": "singular"
        }
        
        response = await async_client.post("/api/config", json=new_config)
        data = response.json()
        
        # Should return updated stats
        assert data["stats"]["total_nodes"] > 0


class TestRootEndpoint:
    """Tests for GET / endpoint."""
    
    @pytest.mark.asyncio
    async def test_root_returns_html(self, async_client):
        """Should return HTML content."""
        response = await async_client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
    
    @pytest.mark.asyncio
    async def test_root_contains_pagdrawer(self, async_client):
        """HTML should contain PAGDrawer title."""
        response = await async_client.get("/")
        content = response.text
        assert "PAGDrawer" in content or "pagdrawer" in content.lower()
