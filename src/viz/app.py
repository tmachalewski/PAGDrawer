"""
FastAPI backend for serving the Knowledge Graph visualization.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import json
import os
import tempfile
import uuid

import yaml

from src.graph.builder import build_knowledge_graph, KnowledgeGraphBuilder
from src.core.config import GraphConfig
from src.data.loaders import (
    TrivyDataLoader,
    DeploymentLoader,
    LoadedData,
    load_trivy_json,
    load_deployment,
)
from src.data.schemas.deployment import DeploymentConfig

app = FastAPI(title="PAGDrawer", description="Knowledge Graph Visualization")


@dataclass
class TrivyScan:
    """Stores a Trivy scan with metadata."""
    id: str
    name: str  # From ArtifactName or filename
    filename: str
    uploaded_at: datetime
    vuln_count: int
    data: Dict[str, Any]


# Global state
graph_builder = None
current_config = GraphConfig()
current_data_source = "mock"  # "mock", "trivy", or "deployment"
uploaded_trivy_scans: List[TrivyScan] = []
uploaded_deployment_config: Optional[Dict[str, Any]] = None
# Cache enriched data so config changes don't lose enrichment
current_loaded_data: Optional[LoadedData] = None


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
async def update_config(config_data: Dict[str, Any]):
    """Update configuration and rebuild graph with current data source."""
    global graph_builder, current_config

    # Update config
    current_config = GraphConfig.from_dict(config_data)

    # Rebuild graph with new config using cached enriched data or mock
    if current_data_source == "mock" or not current_loaded_data:
        # Use mock data
        graph_builder = build_knowledge_graph(current_config)
    else:
        # Reuse cached enriched data (avoids re-loading and losing enrichment)
        try:
            graph_builder = KnowledgeGraphBuilder(config=current_config)
            graph_builder.load_from_data(current_loaded_data)
        except Exception as e:
            print(f"Error rebuilding from cached data: {e}")
            # Fall back to mock data
            graph_builder = build_knowledge_graph(current_config)

    print(f"Graph rebuilt with config: {current_config.to_dict()}")
    print(f"Data source: {current_data_source}, Stats: {graph_builder.get_stats()}")

    return {"status": "ok", "source": current_data_source, "stats": graph_builder.get_stats()}


# =============================================================================
# TRIVY DATA UPLOAD ENDPOINTS
# =============================================================================


@app.post("/api/upload/trivy")
async def upload_trivy_json(file: UploadFile = File(...)):
    """Upload a Trivy JSON scan result.

    Multiple files can be uploaded sequentially. Use /api/data/rebuild
    to rebuild the graph with all uploaded data.
    """
    global uploaded_trivy_scans

    try:
        content = await file.read()
        data = json.loads(content)

        # Validate it's a valid Trivy report
        results = data.get("Results") or data.get("results", [])
        if not results:
            raise HTTPException(
                status_code=400,
                detail="Invalid Trivy JSON: missing 'Results' field"
            )

        # Extract metadata
        artifact_name = data.get("ArtifactName", file.filename or "unknown")
        vuln_count = sum(
            len(result.get("Vulnerabilities", []))
            for result in results
        )

        scan = TrivyScan(
            id=str(uuid.uuid4()),
            name=artifact_name,
            filename=file.filename or "uploaded.json",
            uploaded_at=datetime.now(),
            vuln_count=vuln_count,
            data=data,
        )
        uploaded_trivy_scans.append(scan)

        return {
            "status": "ok",
            "message": "Trivy data uploaded successfully",
            "scan_id": scan.id,
            "name": scan.name,
            "vuln_count": scan.vuln_count,
            "filename": scan.filename,
            "total_uploaded": len(uploaded_trivy_scans),
        }
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload/trivy/json")
async def upload_trivy_json_direct(trivy_data: Dict[str, Any]):
    """Upload Trivy JSON data directly (not as file upload)."""
    global uploaded_trivy_scans

    try:
        results = trivy_data.get("Results") or trivy_data.get("results", [])
        if not results:
            raise HTTPException(
                status_code=400,
                detail="Invalid Trivy JSON: missing 'Results' field"
            )

        # Extract metadata
        artifact_name = trivy_data.get("ArtifactName", "direct-upload")
        vuln_count = sum(
            len(result.get("Vulnerabilities", []))
            for result in results
        )

        scan = TrivyScan(
            id=str(uuid.uuid4()),
            name=artifact_name,
            filename="direct-upload.json",
            uploaded_at=datetime.now(),
            vuln_count=vuln_count,
            data=trivy_data,
        )
        uploaded_trivy_scans.append(scan)

        return {
            "status": "ok",
            "message": "Trivy data uploaded successfully",
            "scan_id": scan.id,
            "name": scan.name,
            "vuln_count": scan.vuln_count,
            "total_uploaded": len(uploaded_trivy_scans),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload/deployment")
async def upload_deployment_config(file: UploadFile = File(...)):
    """Upload a deployment configuration YAML file."""
    global uploaded_deployment_config

    try:
        content = await file.read()
        content_str = content.decode("utf-8")

        # Parse YAML
        data = yaml.safe_load(content_str)

        # Validate by creating DeploymentConfig
        DeploymentConfig.model_validate(data)

        uploaded_deployment_config = data

        return {
            "status": "ok",
            "message": "Deployment config uploaded successfully",
            "filename": file.filename,
            "hosts": len(data.get("hosts", [])),
            "subnets": len(data.get("subnets", [])),
        }
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload/deployment/json")
async def upload_deployment_config_json(deployment_data: Dict[str, Any]):
    """Upload deployment configuration directly as JSON."""
    global uploaded_deployment_config

    try:
        # Validate by creating DeploymentConfig
        DeploymentConfig.model_validate(deployment_data)

        uploaded_deployment_config = deployment_data

        return {
            "status": "ok",
            "message": "Deployment config uploaded successfully",
            "hosts": len(deployment_data.get("hosts", [])),
            "subnets": len(deployment_data.get("subnets", [])),
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid deployment config: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/data/status")
async def get_data_status():
    """Get status of uploaded data."""
    return {
        "current_source": current_data_source,
        "trivy_uploads": len(uploaded_trivy_scans),
        "has_deployment_config": uploaded_deployment_config is not None,
        "deployment_hosts": len(uploaded_deployment_config.get("hosts", [])) if uploaded_deployment_config else 0,
    }


@app.get("/api/data/scans")
async def list_scans():
    """List all uploaded Trivy scans with metadata."""
    return {
        "scans": [
            {
                "id": scan.id,
                "name": scan.name,
                "filename": scan.filename,
                "uploaded_at": scan.uploaded_at.isoformat(),
                "vuln_count": scan.vuln_count,
            }
            for scan in uploaded_trivy_scans
        ]
    }


@app.delete("/api/data/scans/{scan_id}")
async def delete_scan(scan_id: str):
    """Delete a specific scan by ID."""
    global uploaded_trivy_scans
    
    original_count = len(uploaded_trivy_scans)
    uploaded_trivy_scans = [s for s in uploaded_trivy_scans if s.id != scan_id]
    
    if len(uploaded_trivy_scans) == original_count:
        raise HTTPException(status_code=404, detail=f"Scan not found: {scan_id}")
    
    return {"status": "ok", "remaining": len(uploaded_trivy_scans)}


@app.post("/api/data/rebuild")
async def rebuild_from_uploaded_data(
    enrich: bool = True,
    use_deployment: bool = True,
    scan_ids: Optional[List[str]] = Query(default=None),
):
    """Rebuild the graph from uploaded Trivy data and deployment config.

    Args:
        enrich: Whether to enrich data from NVD/CWE sources.
        use_deployment: Whether to use uploaded deployment config.
        scan_ids: Optional list of scan IDs to use. If None, uses all scans.
    """
    global graph_builder, current_data_source, current_config, current_loaded_data

    if not uploaded_trivy_scans:
        raise HTTPException(
            status_code=400,
            detail="No Trivy data uploaded. Use /api/upload/trivy first."
        )

    # Reset config to defaults when rebuilding with new data
    current_config = GraphConfig()

    # Filter scans if scan_ids provided
    scans_to_use = uploaded_trivy_scans
    if scan_ids:
        scans_to_use = [s for s in uploaded_trivy_scans if s.id in scan_ids]
        if not scans_to_use:
            raise HTTPException(
                status_code=400,
                detail="No matching scans found for provided scan_ids"
            )

    # Extract raw data from scans
    trivy_data_list = [scan.data for scan in scans_to_use]

    try:
        if use_deployment and uploaded_deployment_config:
            # Use DeploymentLoader
            loader = DeploymentLoader(
                deployment_config=uploaded_deployment_config,
                trivy_sources=trivy_data_list,
                enrich_from_nvd=enrich,
                enrich_cwe=enrich,
            )
            loaded_data = loader.load()
            current_data_source = "deployment"
        else:
            # Load Trivy data directly without deployment config
            all_data = LoadedData()
            for trivy_json in trivy_data_list:
                data = load_trivy_json(trivy_json, enrich=enrich)
                # Merge data
                all_data.hosts.extend(data.hosts)
                all_data.cpes.extend(data.cpes)
                all_data.cves.extend(data.cves)
                all_data.cwes.extend(data.cwes)
                for host_id, cpe_list in data.host_cpe_map.items():
                    all_data.host_cpe_map.setdefault(host_id, []).extend(cpe_list)
                all_data.network_edges.extend(data.network_edges)
            loaded_data = all_data
            current_data_source = "trivy"

        # Cache enriched data for future config changes
        current_loaded_data = loaded_data

        # Create new builder and load data
        graph_builder = KnowledgeGraphBuilder(config=current_config)
        graph_builder.load_from_data(loaded_data)

        print(f"Graph rebuilt from {current_data_source} data")
        print(f"Using {len(scans_to_use)} scan(s): {[s.name for s in scans_to_use]}")
        print(f"Stats: {graph_builder.get_stats()}")

        return {
            "status": "ok",
            "source": current_data_source,
            "scans_used": len(scans_to_use),
            "stats": graph_builder.get_stats(),
            "config": current_config.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/data/reset")
async def reset_to_mock_data():
    """Reset to using mock data and clear uploaded data."""
    global graph_builder, current_data_source, uploaded_trivy_scans, uploaded_deployment_config, current_config, current_loaded_data

    # Clear uploaded data
    uploaded_trivy_scans = []
    uploaded_deployment_config = None
    current_loaded_data = None

    # Reset config to defaults and rebuild with mock data
    current_config = GraphConfig()
    graph_builder = build_knowledge_graph(current_config)
    current_data_source = "mock"

    print("Reset to mock data")

    return {
        "status": "ok",
        "source": "mock",
        "stats": graph_builder.get_stats(),
    }


@app.delete("/api/data/trivy")
async def clear_trivy_uploads():
    """Clear all uploaded Trivy data."""
    global uploaded_trivy_scans
    uploaded_trivy_scans = []
    return {"status": "ok", "message": "Trivy uploads cleared"}


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

