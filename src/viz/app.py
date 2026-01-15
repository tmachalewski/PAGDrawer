"""
FastAPI backend for serving the Knowledge Graph visualization.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path
from typing import Dict
import json
import os

from src.graph.builder import build_knowledge_graph
from src.core.config import GraphConfig

app = FastAPI(title="PAGDrawer", description="Knowledge Graph Visualization")

# Global state
graph_builder = None
current_config = GraphConfig()


@app.on_event("startup")
async def startup_event():
    global graph_builder, current_config
    graph_builder = build_knowledge_graph(current_config)
    print(f"Graph loaded: {graph_builder.get_stats()}")


def _generate_label(node: dict) -> str:
    """Generate a clean label for display."""
    node_id = node["id"]
    node_type = node.get("node_type", "")
    
    if node_type == "VC":
        # Show just VC type:value (e.g., "AV:N", "PR:H")
        return f"{node.get('vc_type', '')}:{node.get('value', '')}"
    elif node_type == "CVE":
        # Show original CVE ID without @host suffix
        return node.get("original_cve", node_id.split("@")[0])
    elif node_type == "CPE":
        # Show just product name
        return node.get("product", node_id.split("@")[0])
    elif node_type == "HOST":
        # Show host ID
        return node_id
    elif node_type == "CWE":
        # Show original CWE ID
        return node.get("original_cwe", node_id.split("@")[0])
    elif node_type == "ATTACKER":
        return "☠ Hacker"
    else:
        # Default: use ID
        return node_id


@app.get("/api/graph")
async def get_graph():
    """Return the full graph as JSON for Cytoscape.js."""
    data = graph_builder.to_json()
    
    # Transform to Cytoscape.js format
    cytoscape_data = {
        "elements": {
            "nodes": [
                {
                    "data": {
                        "id": node["id"],
                        # Generate clean labels based on node type
                        "label": _generate_label(node),
                        "type": node.get("node_type", "unknown"),
                        **{k: v for k, v in node.items() if k not in ["id", "node_type"]}
                    }
                }
                for node in data["nodes"]
            ],
            "edges": [
                {
                    "data": {
                        "id": f"{edge['source']}->{edge['target']}",
                        "source": edge["source"],
                        "target": edge["target"],
                        "type": edge.get("edge_type", "unknown"),
                        "weight": edge.get("weight", 1.0)
                    }
                }
                for edge in data["edges"]
            ]
        }
    }
    
    return cytoscape_data


@app.get("/api/stats")
async def get_stats():
    """Return graph statistics."""
    return graph_builder.get_stats()


@app.get("/api/config")
async def get_config():
    """Return current graph configuration."""
    return current_config.to_dict()


@app.post("/api/config")
async def update_config(config_data: Dict[str, str]):
    """Update configuration and rebuild graph."""
    global graph_builder, current_config
    
    # Update config
    current_config = GraphConfig.from_dict(config_data)
    
    # Rebuild graph with new config
    graph_builder = build_knowledge_graph(current_config)
    print(f"Graph rebuilt with config: {current_config.to_dict()}")
    print(f"New stats: {graph_builder.get_stats()}")
    
    return {"status": "ok", "stats": graph_builder.get_stats()}


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main visualization page."""
    frontend_path = Path(__file__).parent.parent.parent / "frontend" / "index.html"
    if frontend_path.exists():
        return FileResponse(frontend_path)
    return HTMLResponse("<h1>Frontend not found. Run from project root.</h1>")


# Mount static files for frontend assets
frontend_dir = Path(__file__).parent.parent.parent / "frontend"
if frontend_dir.exists():
    # Mount CSS directory
    css_dir = frontend_dir / "css"
    if css_dir.exists():
        app.mount("/css", StaticFiles(directory=str(css_dir)), name="css")
    
    # Mount JS directory
    js_dir = frontend_dir / "js"
    if js_dir.exists():
        app.mount("/js", StaticFiles(directory=str(js_dir)), name="js")
    
    # Keep general static mount as fallback
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

