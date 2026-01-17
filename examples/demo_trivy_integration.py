#!/usr/bin/env python3
"""
Demo script showing how to use the Trivy integration features.

Run from project root:
    python examples/demo_trivy_integration.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.loaders import (
    DeploymentLoader,
    TrivyDataLoader,
    load_trivy_json,
    load_deployment,
)
from src.graph.builder import KnowledgeGraphBuilder


def demo_simple_trivy_load():
    """Demo 1: Load a single Trivy scan without deployment config."""
    print("=" * 60)
    print("Demo 1: Simple Trivy Load")
    print("=" * 60)

    # Load Trivy JSON (without NVD enrichment for speed)
    trivy_file = Path(__file__).parent / "sample_trivy_scan.json"
    data = load_trivy_json(str(trivy_file), enrich=False)

    print(f"\nLoaded data statistics:")
    print(f"  Hosts: {len(data.hosts)}")
    print(f"  CPEs (packages): {len(data.cpes)}")
    print(f"  CVEs (vulnerabilities): {len(data.cves)}")
    print(f"  CWEs (weakness types): {len(data.cwes)}")

    print(f"\nHosts found:")
    for host in data.hosts:
        print(f"  - {host['id']} ({host['os_family']})")

    print(f"\nVulnerabilities found:")
    for cve in data.cves:
        print(f"  - {cve['id']}: {cve['severity']} - {cve.get('description', '')[:50]}...")

    return data


def demo_deployment_integration():
    """Demo 2: Load Trivy scan with deployment topology."""
    print("\n" + "=" * 60)
    print("Demo 2: Deployment Configuration Integration")
    print("=" * 60)

    examples_dir = Path(__file__).parent
    deployment_file = examples_dir / "sample_deployment.yaml"
    trivy_file = examples_dir / "sample_trivy_scan.json"

    # Load with deployment config
    loader = DeploymentLoader(
        deployment_config=str(deployment_file),
        trivy_sources=[str(trivy_file)],
        enrich_from_nvd=False,
        enrich_cwe=False,
    )
    data = loader.load()

    print(f"\nDeployment: {loader.deployment_config.name}")
    print(f"\nNetwork topology:")
    for subnet in loader.deployment_config.subnets:
        print(f"  [{subnet.id}] {subnet.name or subnet.id}")
        if subnet.connects_to:
            print(f"      -> connects to: {', '.join(subnet.connects_to)}")

    print(f"\nHosts with mapped vulnerabilities:")
    for host in data.hosts:
        cpes = data.host_cpe_map.get(host["id"], [])
        cves_for_host = [c for c in data.cves if c.get("cpe_id") in cpes]
        print(f"  {host['id']} (criticality: {host['criticality_score']})")
        print(f"      Subnet: {host['subnet_id']}")
        print(f"      Packages: {len(cpes)}")
        print(f"      Vulnerabilities: {len(cves_for_host)}")

    print(f"\nNetwork edges: {len(data.network_edges)}")

    return data


def demo_build_graph():
    """Demo 3: Build full attack graph from loaded data."""
    print("\n" + "=" * 60)
    print("Demo 3: Build Attack Graph")
    print("=" * 60)

    examples_dir = Path(__file__).parent
    deployment_file = examples_dir / "sample_deployment.yaml"
    trivy_file = examples_dir / "sample_trivy_scan.json"

    # Load data
    data = load_deployment(
        config_path=str(deployment_file),
        trivy_paths=[str(trivy_file)],
        enrich=False,
    )

    # Build graph
    builder = KnowledgeGraphBuilder()
    builder.load_from_data(data)

    stats = builder.get_stats()
    print(f"\nGraph statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Show node type breakdown
    print(f"\nNodes by type:")
    for node_type, count in stats.get("nodes_by_type", {}).items():
        print(f"  {node_type}: {count}")

    return builder


def demo_api_usage():
    """Demo 4: Show how to use the API endpoints."""
    print("\n" + "=" * 60)
    print("Demo 4: API Usage Examples")
    print("=" * 60)

    print("""
To use via the web API:

1. Start the server:
   uvicorn src.viz.app:app --reload

2. Upload Trivy scan:
   curl -X POST "http://localhost:8000/api/upload/trivy" \\
     -F "file=@examples/sample_trivy_scan.json"

3. Upload deployment config:
   curl -X POST "http://localhost:8000/api/upload/deployment" \\
     -F "file=@examples/sample_deployment.yaml"

4. Check upload status:
   curl "http://localhost:8000/api/data/status"

5. Rebuild graph with uploaded data:
   curl -X POST "http://localhost:8000/api/data/rebuild?enrich=false"

6. View the graph:
   Open http://localhost:8000 in your browser

7. Reset to mock data:
   curl -X POST "http://localhost:8000/api/data/reset"
""")


if __name__ == "__main__":
    print("PAGDrawer - Trivy Integration Demo")
    print("===================================\n")

    # Run demos
    demo_simple_trivy_load()
    demo_deployment_integration()
    demo_build_graph()
    demo_api_usage()

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)
