/**
 * Tooltip for node details
 * Shows separate draggable tooltip boxes with arrows pointing to nodes
 */

import { getCy } from '../graph/core';
import { nodeColors } from '../config/constants';
import type { NodeSingular, EventObject, NodeCollection } from 'cytoscape';

let tooltipContainer: HTMLElement | null = null;
let arrowsContainer: SVGElement | null = null;
let selectedNodes: Set<string> = new Set();
let hoveredNode: NodeSingular | null = null;
let isFilterActive: boolean = false;

// Store node references for arrow updates
let currentNodes: NodeSingular[] = [];

// Store ABSOLUTE screen positions for dragged tooltips (by node ID)
// Once dragged, tooltip is detached from node and uses these fixed coordinates
let draggedPositions: Map<string, { left: number; top: number }> = new Map();

interface NodeData {
    id: string;
    label?: string;
    type?: string;
    [key: string]: unknown;
}

/**
 * Setup tooltip event handlers
 */
export function setupTooltip(): void {
    const cy = getCy();
    if (!cy) return;

    // Create container for multiple tooltips
    tooltipContainer = document.getElementById('node-tooltip');
    if (!tooltipContainer) return;

    // Create SVG container for arrows
    createArrowsContainer();

    // Mouse over any node
    cy.on('mouseover', 'node', handleNodeMouseOver);
    cy.on('mouseout', 'node', handleNodeMouseOut);

    // Node click - select with CTRL support
    cy.on('tap', 'node', handleNodeClick);

    // Background click - clear selection
    cy.on('tap', handleBackgroundClick);

    // Viewport changes - update tooltip positions and arrows
    cy.on('viewport', handleViewportChange);

    // Listen for filter button clicks
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', function (this: HTMLElement) {
            const type = this.dataset.type || 'all';
            isFilterActive = type !== 'all';
            if (isFilterActive) {
                hideAllTooltips();
            }
        });
    });
}

/**
 * Create SVG container for arrows (or reuse existing)
 */
function createArrowsContainer(): void {
    // Check for existing container to avoid duplicates on graph rebuild
    const existing = document.getElementById('tooltip-arrows');
    if (existing) {
        arrowsContainer = existing as unknown as SVGElement;
        return;
    }

    arrowsContainer = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    arrowsContainer.id = 'tooltip-arrows';
    arrowsContainer.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: 9999;
    `;
    document.body.appendChild(arrowsContainer);
}

/**
 * Handle mouse over node
 */
function handleNodeMouseOver(evt: EventObject): void {
    if (isFilterActive) return;

    const node = evt.target as NodeSingular;
    hoveredNode = node;
    updateAllTooltips();
}

/**
 * Handle mouse out
 */
function handleNodeMouseOut(): void {
    if (isFilterActive) return;

    hoveredNode = null;
    updateAllTooltips();
}

/**
 * Handle viewport change (zoom/pan) - only update arrows
 * Tooltips stay fixed on screen, arrows update to point to nodes
 */
function handleViewportChange(): void {
    updateArrows();
}

/**
 * Handle node click - multi-select with CTRL
 */
function handleNodeClick(evt: EventObject): void {
    if (isFilterActive) return;

    const node = evt.target as NodeSingular;
    const originalEvent = evt.originalEvent as MouseEvent;
    const isCtrlPressed = originalEvent?.ctrlKey || originalEvent?.metaKey;
    const cy = getCy();

    if (isCtrlPressed) {
        // Toggle selection
        if (selectedNodes.has(node.id())) {
            selectedNodes.delete(node.id());
            node.unselect();
            node.removeClass('node-selected');
        } else {
            selectedNodes.add(node.id());
            node.select();
            node.addClass('node-selected');
        }
    } else {
        // Single select - clear others
        if (cy) {
            cy.nodes().unselect();
            cy.nodes().removeClass('node-selected');
        }
        selectedNodes.clear();
        selectedNodes.add(node.id());
        node.select();
        node.addClass('node-selected');
    }

    updateAllTooltips();
    updateHighlighting();
}

/**
 * Handle background click - clear selection
 */
function handleBackgroundClick(evt: EventObject): void {
    const cy = getCy();
    if (!cy) return;

    if (evt.target === cy) {
        selectedNodes.clear();
        hoveredNode = null;
        cy.nodes().unselect();
        cy.nodes().removeClass('node-selected');
        cy.elements().removeClass('highlighted faded');
        hideAllTooltips();
    }
}

/**
 * Get collection of selected nodes
 * Uses getElementById instead of CSS selectors for reliable ID handling
 */
function getSelectedNodesCollection(): NodeCollection | null {
    const cy = getCy();
    if (!cy || selectedNodes.size === 0) return null;

    // Use getElementById for each ID - more reliable than CSS selectors for complex IDs
    let collection = cy.collection();
    for (const id of selectedNodes) {
        const node = cy.getElementById(id);
        if (node.length > 0) {
            collection = collection.union(node);
        }
    }

    return collection.length > 0 ? collection : null;
}

/**
 * Update highlighting for selected nodes
 */
function updateHighlighting(): void {
    const cy = getCy();
    if (!cy) return;

    cy.elements().removeClass('highlighted faded');

    if (selectedNodes.size > 0) {
        const selected = getSelectedNodesCollection();
        if (selected) {
            const neighborhood = selected.closedNeighborhood();
            cy.elements().addClass('faded');
            neighborhood.removeClass('faded').addClass('highlighted');
        }
    }
}

/**
 * Update all tooltips - one per node
 */
function updateAllTooltips(): void {
    if (!tooltipContainer || isFilterActive) return;

    // Collect all nodes that need tooltips
    const nodesToShow: NodeSingular[] = [];

    // Add selected nodes
    const selected = getSelectedNodesCollection();
    if (selected) {
        selected.forEach(n => { nodesToShow.push(n); });
    }

    // Add hovered node if not already selected
    if (hoveredNode && !selectedNodes.has(hoveredNode.id())) {
        nodesToShow.push(hoveredNode);
    }

    if (nodesToShow.length === 0) {
        hideAllTooltips();
        return;
    }

    // Store for arrow updates
    currentNodes = nodesToShow;

    // Build HTML for all tooltips with index
    let html = '';
    nodesToShow.forEach((node, index) => {
        html += createTooltipHTML(node, index);
    });

    tooltipContainer.innerHTML = html;
    tooltipContainer.classList.add('visible');

    // Position each tooltip and setup drag after DOM renders
    requestAnimationFrame(() => {
        nodesToShow.forEach((node, index) => {
            positionTooltipByIndex(node, index);
            setupDragForTooltip(node.id(), index);
        });
        updateArrows();
    });
}

/**
 * Create HTML for a single node's tooltip
 */
function createTooltipHTML(node: NodeSingular, index: number): string {
    const data = node.data() as NodeData;
    const nodeType = data.type || 'unknown';
    const nodeColor = nodeColors[nodeType] || '#888';

    let html = `<div class="tooltip-box" data-tooltip-index="${index}">`;
    html += '<div class="tooltip-header"></div>'; // Drag handle
    html += '<div class="tooltip-details">';

    // Show id with node color
    if (data.id) {
        html += `<div class="tooltip-detail-row"><span class="tooltip-detail-key">id:</span> <span class="tooltip-detail-value" style="color: ${nodeColor}">${data.id}</span></div>`;
    }
    if (data.label && data.label !== data.id) {
        html += `<div class="tooltip-detail-row"><span class="tooltip-detail-key">label:</span> <span class="tooltip-detail-value" style="color: ${nodeColor}">${data.label}</span></div>`;
    }

    // Show other properties
    for (const [key, value] of Object.entries(data)) {
        if (key === 'id' || key === 'label') continue;
        if (typeof value === 'string' || typeof value === 'number') {
            html += `<div class="tooltip-detail-row"><span class="tooltip-detail-key">${key}:</span> <span class="tooltip-detail-value">${value}</span></div>`;
        }
    }
    html += '</div>';

    // Add warning section if node is dimmed
    const reasons = getNodeReasons(node);
    if (reasons.length > 0) {
        html += '<div class="tooltip-warning">';
        html += '<div class="tooltip-title">⚠ Why is this grayed out?</div>';
        reasons.forEach(reason => {
            html += `<div class="tooltip-reason">${reason}</div>`;
        });
        html += '</div>';
    }

    html += '</div>';
    return html;
}

/**
 * Setup drag handlers for a tooltip
 */
function setupDragForTooltip(nodeId: string, index: number): void {
    const tooltipBox = document.querySelector(`.tooltip-box[data-tooltip-index="${index}"]`) as HTMLElement;
    if (!tooltipBox) return;

    // Find the node for this tooltip
    const cy = getCy();
    if (!cy) return;
    const node = cy.getElementById(nodeId);
    if (node.empty()) return;

    let isDragging = false;
    let startX = 0;
    let startY = 0;
    let startLeft = 0;
    let startTop = 0;

    const onMouseDown = (e: MouseEvent) => {
        isDragging = true;
        startX = e.clientX;
        startY = e.clientY;
        startLeft = parseInt(tooltipBox.style.left) || 0;
        startTop = parseInt(tooltipBox.style.top) || 0;
        tooltipBox.style.cursor = 'grabbing';
        e.preventDefault();
    };

    const onMouseMove = (e: MouseEvent) => {
        if (!isDragging) return;

        const dx = e.clientX - startX;
        const dy = e.clientY - startY;

        const newLeft = startLeft + dx;
        const newTop = startTop + dy;

        tooltipBox.style.left = newLeft + 'px';
        tooltipBox.style.top = newTop + 'px';

        // Store absolute screen position (detached from node)
        draggedPositions.set(nodeId, { left: newLeft, top: newTop });

        updateArrows();
    };

    const onMouseUp = () => {
        isDragging = false;
        tooltipBox.style.cursor = 'grab';
    };

    tooltipBox.addEventListener('mousedown', onMouseDown);
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
}

/**
 * Position a tooltip relative to its node by index
 * Uses stored absolute position if tooltip was dragged
 */
function positionTooltipByIndex(node: NodeSingular, index: number): void {
    const tooltipBox = document.querySelector(`.tooltip-box[data-tooltip-index="${index}"]`) as HTMLElement;
    if (!tooltipBox) return;

    const nodeId = node.id();

    // Check for stored dragged position (absolute screen coordinates)
    const draggedPos = draggedPositions.get(nodeId);
    if (draggedPos) {
        // Use stored absolute position - completely detached from node
        tooltipBox.style.left = draggedPos.left + 'px';
        tooltipBox.style.top = draggedPos.top + 'px';
        return;
    }

    // Default positioning: relative to node
    const cyContainer = document.getElementById('cy');
    if (!cyContainer) return;

    const rect = cyContainer.getBoundingClientRect();
    const position = node.renderedPosition();
    const x = rect.left + position.x + 40;
    const y = rect.top + position.y - 30;

    // Keep within viewport
    const tooltipRect = tooltipBox.getBoundingClientRect();
    const maxX = window.innerWidth - tooltipRect.width - 10;
    const maxY = window.innerHeight - tooltipRect.height - 10;

    tooltipBox.style.left = Math.min(x, maxX) + 'px';
    tooltipBox.style.top = Math.max(10, Math.min(y, maxY)) + 'px';
}

/**
 * Update all arrows from tooltips to nodes
 */
function updateArrows(): void {
    if (!arrowsContainer) return;

    // Clear existing arrows
    arrowsContainer.innerHTML = '';

    const cyContainer = document.getElementById('cy');
    if (!cyContainer) return;

    const rect = cyContainer.getBoundingClientRect();

    currentNodes.forEach((node, index) => {
        const tooltipBox = document.querySelector(`.tooltip-box[data-tooltip-index="${index}"]`) as HTMLElement;
        if (!tooltipBox) return;

        const tooltipRect = tooltipBox.getBoundingClientRect();
        const position = node.renderedPosition();

        // Arrow from top-left corner of tooltip to node center
        const startX = tooltipRect.left;
        const startY = tooltipRect.top;
        const endX = rect.left + position.x;
        const endY = rect.top + position.y;

        // Create dashed line
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', String(startX));
        line.setAttribute('y1', String(startY));
        line.setAttribute('x2', String(endX));
        line.setAttribute('y2', String(endY));
        line.setAttribute('stroke', 'rgba(100, 100, 200, 0.7)');
        line.setAttribute('stroke-width', '2');
        line.setAttribute('stroke-dasharray', '6 4');

        if (arrowsContainer) {
            arrowsContainer.appendChild(line);
        }

        // Create small circle at tooltip corner
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', String(startX));
        circle.setAttribute('cy', String(startY));
        circle.setAttribute('r', '4');
        circle.setAttribute('fill', 'rgba(100, 100, 200, 0.9)');

        if (arrowsContainer) {
            arrowsContainer.appendChild(circle);
        }
    });
}

/**
 * Get warning reasons for a node
 */
function getNodeReasons(node: NodeSingular): string[] {
    const reasons: string[] = [];

    if (node.hasClass('unreachable')) {
        reasons.push('Cannot exploit until attacker gains foothold in the network');
    }

    if (node.hasClass('env-filtered')) {
        reasons.push('Not exploitable with current environment settings (UI/AC)');
    }

    return reasons;
}

/**
 * Hide all tooltips
 */
function hideAllTooltips(): void {
    if (tooltipContainer) {
        tooltipContainer.innerHTML = '';
        tooltipContainer.classList.remove('visible');
    }
    if (arrowsContainer) {
        arrowsContainer.innerHTML = '';
    }
    currentNodes = [];
}

/**
 * Clear the selected nodes (called when graph is rebuilt)
 */
export function clearSelectedNode(): void {
    selectedNodes.clear();
    hoveredNode = null;
    isFilterActive = false;
    draggedPositions.clear();
    hideAllTooltips();
}

/**
 * Set filter active state
 */
export function setFilterActive(active: boolean): void {
    isFilterActive = active;
    if (active) {
        hideAllTooltips();
    }
}
