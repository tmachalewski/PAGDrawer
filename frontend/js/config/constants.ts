/**
 * Constants and configuration for PAGDrawer
 */

import type { NodeSingular, EdgeSingular } from 'cytoscape';

// Node colors by type
export const nodeColors: Record<string, string> = {
    HOST: '#ef4444',
    CPE: '#f97316',
    CVE: '#eab308',
    CWE: '#22c55e',
    TI: '#00bfff',
    VC: '#6366f1',
    ATTACKER: '#ff0066',
    BRIDGE: '#00ff88'
};

// Edge colors by type
export const edgeColors: Record<string, string> = {
    RUNS: '#ef4444',
    HAS_VULN: '#f97316',
    IS_INSTANCE_OF: '#22c55e',
    HAS_IMPACT: '#00bfff',
    CONNECTED_TO: '#888888',
    ALLOWS_EXPLOIT: '#6366f1',
    YIELDS_STATE: '#a855f7',
    LEADS_TO: '#a855f7',
    ENABLES: '#00ffff',
    PIVOTS_TO: '#ff9900',
    BRIDGE: '#00ffff',
    ATTACKS_FROM: '#ff0066',
    HAS_STATE: '#ff0066',
    CAN_REACH: '#ff6600',
    ENTERS_NETWORK: '#00ff88'
};

// Cytoscape style definitions
export function getCytoscapeStyles(): any[] {
    return [
        {
            selector: 'node',
            style: {
                'background-color': (ele: NodeSingular) => nodeColors[ele.data('type')] || '#666666',
                'label': 'data(label)',
                'color': '#ffffff',
                'text-outline-color': '#000000',
                'text-outline-width': 2,
                'font-size': '10px',
                'width': (ele: NodeSingular) => {
                    const type = ele.data('type');
                    return type === 'HOST' ? 40 : type === 'ATTACKER' ? 45 : type === 'CVE' ? 35 : 30;
                },
                'height': (ele: NodeSingular) => {
                    const type = ele.data('type');
                    return type === 'HOST' ? 40 : type === 'ATTACKER' ? 45 : type === 'CVE' ? 35 : 30;
                },
                'border-width': 2,
                'border-color': '#ffffff20'
            }
        },
        {
            selector: 'edge',
            style: {
                'width': 2,
                'line-color': (ele: EdgeSingular) => edgeColors[ele.data('type')] || '#666666',
                'target-arrow-color': (ele: EdgeSingular) => edgeColors[ele.data('type')] || '#666666',
                'target-arrow-shape': 'triangle',
                'curve-style': 'bezier',
                'opacity': 0.7
            }
        },
        {
            selector: ':selected',
            style: {
                'border-width': 4,
                'border-color': '#ffffff'
            }
        },
        {
            selector: '.highlighted',
            style: {
                'opacity': 1,
                'z-index': 999
            }
        },
        {
            selector: '.faded',
            style: {
                'opacity': 0.2
            }
        },
        {
            selector: 'node[?is_compound]',
            style: {
                'background-color': 'rgba(100, 100, 100, 0.3)',
                'border-width': 2,
                'border-color': '#888888',
                'border-style': 'dashed',
                'shape': 'roundrectangle',
                'padding': '15px',
                'text-valign': 'top',
                'text-halign': 'center',
                'font-size': '12px',
                'color': '#cccccc'
            }
        },
        {
            selector: 'node[?is_initial]',
            style: {
                'border-width': 2,
                'border-color': '#ff0066',
                'border-style': 'solid'
            }
        },
        {
            selector: '.exploit-hidden',
            style: {
                'display': 'none'
            }
        },
        {
            selector: '.export-hidden',
            style: {
                'display': 'none'
            }
        },
        {
            selector: '.env-filtered',
            style: {
                'opacity': 0.25,
                'border-style': 'dashed',
                'border-color': '#ff6666'
            }
        },
        {
            selector: '.unreachable',
            style: {
                'opacity': 0.3,
                'border-style': 'dotted',
                'border-color': '#555555'
            }
        },
        {
            selector: '.unreachable.node-selected',
            style: {
                'opacity': 0.6,
                'border-width': 4,
                'border-color': '#ffffff'
            }
        },
        {
            selector: '.faded-unreachable',
            style: {
                'opacity': 0.15,
                'border-style': 'dotted',
                'border-color': '#333333'
            }
        },
        {
            selector: '.search-match',
            style: {
                'border-width': 4,
                'border-color': '#ffd700',
                'overlay-color': '#ffd700',
                'overlay-opacity': 0.2,
                'z-index': 999
            }
        },
        {
            selector: '.search-dimmed',
            style: {
                'opacity': 0.15
            }
        },
        {
            selector: 'edge[?isBridge]',
            style: {
                'line-style': 'dashed',
                'line-dash-pattern': [6, 3],
                'width': 3,
                'opacity': 0.9,
                'line-color': (ele: EdgeSingular) => ele.data('bridgeColor') || '#00ffff',
                'target-arrow-color': (ele: EdgeSingular) => ele.data('bridgeColor') || '#00ffff'
            }
        },
        {
            selector: '[type="CVE_GROUP"]',
            style: {
                'background-color': 'rgba(234, 179, 8, 0.12)',
                'border-color': '#eab308',
                'border-width': 2,
                'border-style': 'dashed',
                'label': 'data(label)',
                'text-valign': 'top',
                'text-halign': 'center',
                'font-size': '10px',
                'color': '#eab308',
                'text-outline-color': '#000000',
                'text-outline-width': 1,
                'padding': '12px',
                'shape': 'round-rectangle'
            }
        },
        {
            selector: 'node[?is_terminal]',
            style: {
                'background-color': '#ff0000',
                'border-width': 4,
                'border-color': '#ffd700',
                'shape': 'star',
                'width': 50,
                'height': 50,
                'font-weight': 'bold'
            }
        },
        {
            selector: 'node[?is_phase_separator]',
            style: {
                'background-color': '#00ff88',
                'border-width': 4,
                'border-color': '#00cc66',
                'shape': 'diamond',
                'width': 60,
                'height': 60,
                'font-size': '14px',
                'font-weight': 'bold',
                'text-outline-width': 3
            }
        }
    ];
}
