/**
 * Shared TypeScript type definitions for PAGDrawer
 */

import type { Core, NodeSingular, EdgeSingular, EventObject } from 'cytoscape';

// Node types in the graph
export type NodeType = 'HOST' | 'CPE' | 'CVE' | 'CWE' | 'TI' | 'VC' | 'ATTACKER' | 'BRIDGE' | 'COMPOUND';

// Edge types in the graph
export type EdgeType = 'CAN_REACH' | 'RUNS' | 'HAS_VULN' | 'IS_INSTANCE_OF' | 'HAS_IMPACT' | 'LEADS_TO' | 'ENABLES' | 'HAS_STATE';

// Graph node data structure
export interface GraphNodeData {
    id: string;
    type: NodeType;
    label: string;
    parent?: string;
    [key: string]: unknown;
}

// Graph edge data structure
export interface GraphEdgeData {
    id: string;
    source: string;
    target: string;
    type: EdgeType;
}

// Graph data from API
export interface GraphData {
    elements: {
        nodes: Array<{ data: GraphNodeData }>;
        edges: Array<{ data: GraphEdgeData }>;
    };
}

// Stats from API
export interface Stats {
    total_nodes: number;
    total_edges: number;
    nodes_by_type: Record<string, number>;
}

// Environment settings
export type UIValue = 'N' | 'R';
export type ACValue = 'L' | 'H';

// Re-export Cytoscape types for convenience
export type { Core, NodeSingular, EdgeSingular, EventObject };
