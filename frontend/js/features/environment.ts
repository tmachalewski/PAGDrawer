/**
 * Environment filtering (UI/AC) with cascade
 */

import { getCy } from '../graph/core';
import { compactCompoundChildren } from '../graph/layout';
import type { Core, NodeSingular } from 'cytoscape';

/**
 * Setup environment filter listeners
 */
export function setupEnvironmentListeners(): void {
    const uiSelect = document.getElementById('env-ui') as HTMLSelectElement | null;
    const acSelect = document.getElementById('env-ac') as HTMLSelectElement | null;

    if (uiSelect) uiSelect.addEventListener('change', applyEnvironmentFilter);
    if (acSelect) acSelect.addEventListener('change', applyEnvironmentFilter);
}

/**
 * Apply environment filter based on UI/AC settings
 */
export function applyEnvironmentFilter(): void {
    const cy = getCy();
    if (!cy) return;

    const uiSelect = document.getElementById('env-ui') as HTMLSelectElement | null;
    const acSelect = document.getElementById('env-ac') as HTMLSelectElement | null;

    const uiSetting = uiSelect?.value || 'N';
    const acSetting = acSelect?.value || 'L';

    // Update the environment VC nodes and compact the attacker box
    updateEnvironmentVCs(uiSetting, acSetting);
    compactCompoundChildren(cy);

    // Clear all filter classes
    cy.elements().removeClass('env-filtered unreachable');

    // Track filtered CVEs
    const filteredCVEs = new Set<string>();

    // Filter CVEs based on CVSS requirements
    cy.nodes('[type="CVE"]').forEach(node => {
        const cvssVector = node.data('cvss_vector') as string || '';

        const uiMatch = cvssVector.match(/UI:([NR])/);
        const cvssUI = uiMatch ? uiMatch[1] : 'N';

        const acMatch = cvssVector.match(/AC:([LH])/);
        const cvssAC = acMatch ? acMatch[1] : 'L';

        const uiMet = (cvssUI === 'N') || (uiSetting === 'R');
        const acMet = (cvssAC === 'L') || (acSetting === 'H');

        if (!(uiMet && acMet)) {
            node.addClass('env-filtered');
            filteredCVEs.add(node.id());
        }
    });

    // Cascade filter: CWE nodes connected only to filtered CVEs
    cy.nodes('[type="CWE"]').forEach(cweNode => {
        const connectedCVEs = cweNode.incomers('node[type="CVE"]').nodes().toArray() as NodeSingular[];
        const allFiltered = connectedCVEs.every(cve => filteredCVEs.has(cve.id()));
        if (connectedCVEs.length > 0 && allFiltered) {
            cweNode.addClass('env-filtered');
            cweNode.connectedEdges().addClass('env-filtered');
        }
    });

    // Cascade filter: TI nodes connected only to filtered CWEs
    cy.nodes('[type="TI"]').forEach(tiNode => {
        const connectedCWEs = tiNode.incomers('node[type="CWE"]').nodes().toArray() as NodeSingular[];
        const allFiltered = connectedCWEs.every(cwe => cwe.hasClass('env-filtered'));
        if (connectedCWEs.length > 0 && allFiltered) {
            tiNode.addClass('env-filtered');
            tiNode.connectedEdges().addClass('env-filtered');
        }
    });

    // Cascade filter: VC nodes with no allowed paths
    cy.nodes('[type="VC"]').forEach(vcNode => {
        if (vcNode.data('is_initial') || vcNode.data('parent') === 'ATTACKER_BOX') {
            return;
        }
        const connectedTIs = vcNode.incomers('node[type="TI"]').nodes().toArray() as NodeSingular[];
        const allFiltered = connectedTIs.every(ti => ti.hasClass('env-filtered'));
        if (connectedTIs.length > 0 && allFiltered) {
            vcNode.addClass('env-filtered');
            vcNode.connectedEdges().addClass('env-filtered');
        }
    });

    // =========================================================================
    // REACHABILITY FILTERING
    // Dim L1 hosts that the attacker cannot reach (no CAN_REACH edge)
    // =========================================================================
    applyReachabilityFilter(cy);
}

/**
 * Apply reachability filter - dim hosts not directly reachable from ATTACKER
 * Only hosts with CAN_REACH edge from ATTACKER are fully visible
 * 
 * Algorithm: BFS from ATTACKER to find all reachable nodes, then mark
 * everything not in that set as unreachable.
 */
function applyReachabilityFilter(cy: Core): void {
    // Find the ATTACKER node
    const attackerNode = cy.nodes('[type="ATTACKER"]').first();
    if (attackerNode.empty()) return;

    // Get all hosts that ATTACKER can reach via CAN_REACH edges
    const reachableHostIds = new Set<string>();
    attackerNode.outgoers('edge[type="CAN_REACH"]').forEach(edge => {
        reachableHostIds.add(edge.target().id());
    });

    // Also add any hosts specifically connected via CAN_REACH
    attackerNode.connectedEdges().forEach(edge => {
        if (edge.data('type') === 'CAN_REACH') {
            const target = edge.target();
            if (target.data('type') === 'HOST') {
                reachableHostIds.add(target.id());
            }
        }
    });

    console.log('Reachable hosts:', Array.from(reachableHostIds));

    // Phase 1: Find ALL reachable nodes using BFS from ATTACKER
    const reachableNodes = new Set<string>();

    // Start from ATTACKER and all reachable hosts
    const queue: NodeSingular[] = [attackerNode];
    reachableNodes.add(attackerNode.id());

    // Add all reachable L1 hosts and their :INSIDE_NETWORK counterparts
    cy.nodes('[type="HOST"]').forEach(hostNode => {
        const hostId = hostNode.id();
        if (reachableHostIds.has(hostId)) {
            reachableNodes.add(hostId);
            queue.push(hostNode);
        }
        // L2 hosts (via INSIDE_NETWORK bridge) are always reachable
        if (hostId.includes(':INSIDE_NETWORK')) {
            reachableNodes.add(hostId);
            queue.push(hostNode);
        }
    });

    // Add ATTACKER_BOX compound and its children
    cy.nodes('[type="COMPOUND"]').forEach(n => { reachableNodes.add(n.id()); });
    cy.nodes('[type="BRIDGE"]').forEach(n => {
        reachableNodes.add(n.id());
        queue.push(n);
    });
    cy.nodes('[parent="ATTACKER_BOX"]').forEach(n => { reachableNodes.add(n.id()); });

    // BFS to find all nodes reachable from the starting set
    while (queue.length > 0) {
        const current = queue.shift()!;

        current.outgoers('node').forEach(successor => {
            if (!reachableNodes.has(successor.id())) {
                reachableNodes.add(successor.id());
                queue.push(successor);
            }
        });
    }

    // Phase 2: Mark all nodes NOT in the reachable set as unreachable
    cy.nodes().forEach(node => {
        if (!reachableNodes.has(node.id())) {
            node.addClass('unreachable');
            node.connectedEdges().addClass('unreachable');
        }
    });

    // Also mark edges between unreachable nodes
    cy.edges().forEach(edge => {
        const source = edge.source();
        const target = edge.target();
        if (source.hasClass('unreachable') && target.hasClass('unreachable')) {
            edge.addClass('unreachable');
        }
    });
}


/**
 * Update or create environment VC nodes (UI/AC) in the attacker box.
 *
 * These use a stable ID scheme: when the setting changes (e.g. UI:N → UI:R),
 * the old node is removed and a new one is created with the updated ID/label.
 */
function updateEnvironmentVCs(uiSetting: string, acSetting: string): void {
    const cy = getCy();
    if (!cy) return;

    upsertEnvVC(cy, 'UI', uiSetting,
        uiSetting === 'R' ? 'User interaction available' : 'No user interaction');
    upsertEnvVC(cy, 'AC', acSetting,
        acSetting === 'H' ? 'High complexity tolerable' : 'Only low complexity');
}

/**
 * Create or update a single environment VC node.
 * Removes the previous node for this vc_type if the value changed.
 */
function upsertEnvVC(cy: any, vcType: string, value: string, description: string): void {
    const newId = `VC:${vcType}:${value}`;
    const label = `${vcType}:${value}`;

    // Check if the correct node already exists
    const existing = cy.getElementById(newId);
    if (existing.length > 0 && existing.data('is_env')) {
        return; // Already correct
    }

    // Remove any previous env node for this vc_type
    cy.nodes('[type="VC"]').forEach((n: any) => {
        if (n.data('is_env') && n.data('vc_type') === vcType) {
            n.connectedEdges().remove();
            n.remove();
        }
    });

    // Find position near existing ATTACKER_BOX children
    const siblings = cy.nodes('[parent="ATTACKER_BOX"]');
    let posX = 0, posY = 0;
    if (siblings.length > 0) {
        const bb = siblings.boundingBox();
        posX = bb.x1 + bb.w / 2;
        posY = bb.y2 + 45; // below existing siblings
    }

    // Create new node
    cy.add({
        group: 'nodes',
        data: {
            id: newId,
            type: 'VC',
            node_type: 'VC',
            vc_type: vcType,
            value: value,
            label: label,
            description: description,
            parent: 'ATTACKER_BOX',
            is_initial: true,
            is_env: true
        },
        position: { x: posX, y: posY }
    });
    cy.add({
        group: 'edges',
        data: {
            source: newId,
            target: 'ATTACKER',
            type: 'HAS_STATE',
            edge_type: 'HAS_STATE'
        }
    });
}
