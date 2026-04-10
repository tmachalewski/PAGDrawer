/**
 * PAGDrawer - Main Entry Point
 * Knowledge Graph Visualization
 */

import { fetchGraph, fetchStats } from './services/api';
import { initCytoscape, getCy } from './graph/core';
import { runLayout, changeLayout, fitView } from './graph/layout';
import { setupEventHandlers } from './graph/events';
import { setupFilterButtons } from './features/filter';
import { setupEnvironmentListeners, applyEnvironmentFilter } from './features/environment';
import { hideSelectedNodes, restoreAllNodes } from './features/hideRestore';
import { toggleExploitPaths } from './features/exploitPaths';
import { initDataSource, triggerFileUpload, rebuildGraph, resetToMock, deleteScanItem } from './features/dataSource';
import { setupSearch, clearSearch } from './features/search';
import { exportSelectedSvg } from './features/exportSvg';
import { toggleTheme } from './features/theme';
import { openSettings, closeSettings, saveSettings } from './ui/modal';
import { updateStats, hideLoading, showError } from './ui/sidebar';
import { setupTooltip } from './ui/tooltip';
import type { Core } from 'cytoscape';

// Extend Window interface for global functions
declare global {
    interface Window {
        cy: Core | null;
        getCy: typeof getCy;
        changeLayout: typeof changeLayout;
        runLayout: typeof runLayout;
        fitView: typeof fitView;
        hideSelectedNodes: typeof hideSelectedNodes;
        restoreAllNodes: typeof restoreAllNodes;
        toggleExploitPaths: typeof toggleExploitPaths;
        openSettings: typeof openSettings;
        closeSettings: typeof closeSettings;
        saveSettings: typeof saveSettings;
        triggerFileUpload: typeof triggerFileUpload;
        rebuildGraph: typeof rebuildGraph;
        resetToMock: typeof resetToMock;
        deleteScanItem: typeof deleteScanItem;
        clearSearch: typeof clearSearch;
        exportSelectedSvg: typeof exportSelectedSvg;
        toggleTheme: typeof toggleTheme;
    }
}

/**
 * Initialize the application
 */
async function init(): Promise<void> {
    try {
        // Fetch graph data and stats
        const [graphData, stats] = await Promise.all([
            fetchGraph(),
            fetchStats()
        ]);

        // Update stats display
        updateStats(stats);

        // Initialize Cytoscape
        initCytoscape(graphData.elements);

        // Apply layout after a short delay
        setTimeout(() => runLayout(), 100);

        // Hide loading overlay
        hideLoading();

        // Setup event handlers
        setupEventHandlers();

        // Setup filter buttons
        setupFilterButtons();

        // Setup environment listeners
        setupEnvironmentListeners();

        // Apply initial environment filter
        applyEnvironmentFilter();

        // Setup tooltip for dimmed nodes
        setupTooltip();

        // Initialize data source panel
        initDataSource();

        // Setup node search
        setupSearch();

        // Expose cy instance for testing
        window.cy = getCy();

        console.log('PAGDrawer initialized successfully');

    } catch (error) {
        console.error('Error loading graph:', error);
        showError('Error loading graph');
    }
}

// Expose functions to global scope for inline HTML handlers
window.changeLayout = changeLayout;
window.runLayout = runLayout;
window.fitView = fitView;
window.hideSelectedNodes = hideSelectedNodes;
window.restoreAllNodes = restoreAllNodes;
window.toggleExploitPaths = toggleExploitPaths;
window.openSettings = openSettings;
window.closeSettings = closeSettings;
window.saveSettings = saveSettings;
window.triggerFileUpload = triggerFileUpload;
window.rebuildGraph = rebuildGraph;
window.resetToMock = resetToMock;
window.deleteScanItem = deleteScanItem;
window.clearSearch = clearSearch;  // Expose for HTML
window.exportSelectedSvg = exportSelectedSvg;  // Expose for HTML
window.toggleTheme = toggleTheme;  // Expose for HTML
window.getCy = getCy;  // Expose for testing

// Initialize on page load
init();
