/**
 * SVG Export for selected graph elements
 *
 * Exports selected nodes (and edges between them) as an SVG file.
 * If nothing is selected, exports the entire visible graph.
 */

import { getCy } from '../graph/core';
import { getTheme } from './theme';
import type { Core } from 'cytoscape';

// Register cytoscape-svg extension
import cytoscapeSvg from 'cytoscape-svg';

let extensionRegistered = false;

function ensureExtension(): void {
    if (!extensionRegistered) {
        const cytoscape = (window as any).cytoscape;
        if (cytoscape) {
            cytoscapeSvg(cytoscape);
            extensionRegistered = true;
        }
    }
}

/**
 * Export selected elements (or all visible) as SVG and trigger download
 */
export function exportSelectedSvg(): void {
    const cy = getCy();
    if (!cy) return;

    ensureExtension();

    const selected = cy.nodes(':selected');
    const hasSelection = selected.length > 0;

    // Determine which elements to export
    let exportNodes: any;
    let exportEdges: any;

    if (hasSelection) {
        exportNodes = selected;
        // Include edges where both source and target are in the selection
        exportEdges = cy.edges().filter(edge => {
            return selected.contains(edge.source()) && selected.contains(edge.target());
        });
    } else {
        // Export all visible elements
        exportNodes = cy.nodes(':visible');
        exportEdges = cy.edges(':visible');
    }

    if (exportNodes.length === 0) {
        alert('No nodes to export. Select nodes first or ensure nodes are visible.');
        return;
    }

    // Elements NOT being exported — temporarily hide them
    const hiddenNodes = cy.nodes().not(exportNodes);
    const hiddenEdges = cy.edges().not(exportEdges);

    hiddenNodes.addClass('export-hidden');
    hiddenEdges.addClass('export-hidden');

    try {
        // Generate SVG using cytoscape-svg extension
        const bg = getTheme() === 'light' ? '#ffffff' : '#0f0f23';
        const svgContent = (cy as any).svg({
            full: true,
            scale: 2,
            bg,
        });

        downloadSvg(svgContent, generateFilename(hasSelection, exportNodes.length));
    } catch (error) {
        console.error('SVG export failed:', error);
        alert('SVG export failed: ' + (error as Error).message);
    } finally {
        // Restore hidden elements
        hiddenNodes.removeClass('export-hidden');
        hiddenEdges.removeClass('export-hidden');
    }
}

/**
 * Generate a descriptive filename
 */
function generateFilename(isPartial: boolean, nodeCount: number): string {
    const timestamp = new Date().toISOString().slice(0, 16).replace(/[T:]/g, '-');
    const scope = isPartial ? `selection-${nodeCount}nodes` : 'full-graph';
    return `pagdrawer-${scope}-${timestamp}.svg`;
}

/**
 * Trigger SVG file download
 */
function downloadSvg(svgContent: string, filename: string): void {
    const blob = new Blob([svgContent], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    URL.revokeObjectURL(url);
}
