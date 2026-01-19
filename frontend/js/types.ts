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

// Upload response from API
export interface UploadResponse {
    status: string;
    message: string;
    scan_id?: string;
    name?: string;
    vuln_count?: number;
    filename?: string;
    total_uploaded: number;
}

// Rebuild response from API
export interface RebuildResponse {
    status: string;
    source: string;
    stats: Stats;
}

// Data status from API
export interface DataStatus {
    current_source: string;
    trivy_uploads: number;
    has_deployment_config: boolean;
    deployment_hosts: number;
}

// Scan info from API
export interface ScanInfo {
    id: string;
    name: string;
    filename: string;
    uploaded_at: string;
    vuln_count: number;
}

// Scans list response
export interface ScansResponse {
    scans: ScanInfo[];
}

// Re-export Cytoscape types for convenience
export type { Core, NodeSingular, EdgeSingular, EventObject };
