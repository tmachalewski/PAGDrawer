"""
PAGDrawer - Main entry point for testing graph construction.
"""

import json
from src.graph.builder import build_knowledge_graph


def main():
    print("=" * 60)
    print("PAGDrawer - Building Knowledge Graph")
    print("=" * 60)
    
    # Build the graph
    builder = build_knowledge_graph()
    
    # Print statistics
    stats = builder.get_stats()
    print(f"\n📊 Graph Statistics:")
    print(f"   Total Nodes: {stats['total_nodes']}")
    print(f"   Total Edges: {stats['total_edges']}")
    
    print(f"\n   Node Types:")
    for node_type, count in stats['node_counts'].items():
        print(f"      {node_type}: {count}")
    
    print(f"\n   Edge Types:")
    for edge_type, count in stats['edge_counts'].items():
        print(f"      {edge_type}: {count}")
    
    # Export to GEXF for Gephi
    gexf_path = "output/knowledge_graph.gexf"
    import os
    os.makedirs("output", exist_ok=True)
    builder.export_gexf(gexf_path)
    print(f"\n✅ Exported to {gexf_path}")
    
    # Export to JSON for browser viz
    json_path = "output/knowledge_graph.json"
    with open(json_path, "w") as f:
        json.dump(builder.to_json(), f, indent=2)
    print(f"✅ Exported to {json_path}")
    
    print("\n" + "=" * 60)
    print("Graph construction complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
