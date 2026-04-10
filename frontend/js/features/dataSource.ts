/**
 * Data Source Management Feature
 * Handles Trivy file uploads, scan selection, and graph rebuilding from the UI
 */

import { uploadTrivyFile, rebuildData, resetData, getDataStatus, getScans, deleteScan, fetchGraph, fetchStats } from '../services/api';
import { initCytoscape, destroyCytoscape } from '../graph/core';
import { runLayout } from '../graph/layout';
import { setupEventHandlers } from '../graph/events';
import { updateStats } from '../ui/sidebar';
import { reapplyHiddenTypes } from './filter';
import { applyEnvironmentFilter } from './environment';
import { syncSlidersFromConfig } from '../ui/modal';
import { setupTooltip, clearSelectedNode } from '../ui/tooltip';
import { clearHiddenElements } from './hideRestore';

/**
 * Initialize data source panel - fetch and display current status
 */
export function initDataSource(): void {
    refreshDataStatus();
    refreshScanList();
    setupFileInput();
}

/**
 * Setup file input change handler
 */
function setupFileInput(): void {
    const fileInput = document.getElementById('trivy-file-input') as HTMLInputElement;
    if (fileInput) {
        fileInput.addEventListener('change', handleFileSelect);
    }
}

/**
 * Trigger file upload dialog
 */
export function triggerFileUpload(): void {
    const fileInput = document.getElementById('trivy-file-input') as HTMLInputElement;
    fileInput?.click();
}

/**
 * Handle file selection and upload
 */
async function handleFileSelect(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    setStatus('Uploading...', 'pending');

    try {
        const result = await uploadTrivyFile(file);
        setStatus(`✅ Uploaded: ${result.name || file.name}`, 'success');
        enableRebuildButton();
        await refreshDataStatus();
        await refreshScanList();
        console.log('Trivy file uploaded:', result);
    } catch (error) {
        const message = error instanceof Error ? error.message : 'Upload failed';
        setStatus(`❌ ${message}`, 'error');
        console.error('Upload error:', error);
    }

    // Clear input to allow re-uploading the same file
    input.value = '';
}

/**
 * Get selected scan IDs for rebuild
 */
function getSelectedScanIds(): string[] | undefined {
    const selector = document.getElementById('scan-selector') as HTMLSelectElement;
    if (!selector || selector.value === 'all') {
        return undefined;  // Use all scans
    }
    return [selector.value];
}

/**
 * Rebuild graph from uploaded data
 */
export async function rebuildGraph(): Promise<void> {
    const enrichCheckbox = document.getElementById('enrich-checkbox') as HTMLInputElement;
    const enrich = enrichCheckbox?.checked ?? true;
    const scanIds = getSelectedScanIds();

    const statusMsg = enrich
        ? 'Rebuilding with enrichment (may take a minute)...'
        : 'Rebuilding...';
    setStatus(statusMsg, 'pending');
    disableRebuildButton();

    try {
        await rebuildData(enrich, scanIds);

        // Reload graph with new data
        const [graphData, stats] = await Promise.all([fetchGraph(), fetchStats()]);
        clearSelectedNode();
        clearHiddenElements();
        destroyCytoscape();
        initCytoscape(graphData.elements);
        setupEventHandlers();
        setupTooltip();
        setTimeout(() => {
            runLayout();
            reapplyHiddenTypes();
            applyEnvironmentFilter();
        }, 100);
        updateStats(stats);

        // Sync sliders to match reset backend config
        await syncSlidersFromConfig();

        setStatus('✅ Graph rebuilt successfully', 'success');
        await refreshDataStatus();
        console.log('Graph rebuilt with enrich=' + enrich + ', scanIds=' + (scanIds || 'all'));
    } catch (error) {
        const message = error instanceof Error ? error.message : 'Rebuild failed';
        setStatus(`❌ ${message}`, 'error');
        enableRebuildButton();
        console.error('Rebuild error:', error);
    }
}

/**
 * Reset to mock data
 */
export async function resetToMock(): Promise<void> {
    setStatus('Resetting to mock data...', 'pending');

    try {
        await resetData();

        // Reload graph with mock data
        const [graphData, stats] = await Promise.all([fetchGraph(), fetchStats()]);
        clearSelectedNode();
        clearHiddenElements();
        destroyCytoscape();
        initCytoscape(graphData.elements);
        setupEventHandlers();
        setupTooltip();
        setTimeout(() => {
            runLayout();
            reapplyHiddenTypes();
            applyEnvironmentFilter();
        }, 100);
        updateStats(stats);

        // Sync sliders to match reset backend config
        await syncSlidersFromConfig();

        setStatus('✅ Reset to mock data', 'success');
        await refreshDataStatus();
        await refreshScanList();
        disableRebuildButton();
        console.log('Reset to mock data');
    } catch (error) {
        const message = error instanceof Error ? error.message : 'Reset failed';
        setStatus(`❌ ${message}`, 'error');
        console.error('Reset error:', error);
    }
}

/**
 * Delete a specific scan and refresh list
 */
export async function deleteScanItem(scanId: string): Promise<void> {
    try {
        await deleteScan(scanId);
        await refreshDataStatus();
        await refreshScanList();
        setStatus('✅ Scan deleted', 'success');
    } catch (error) {
        const message = error instanceof Error ? error.message : 'Delete failed';
        setStatus(`❌ ${message}`, 'error');
        console.error('Delete error:', error);
    }
}

/**
 * Refresh and display scan list
 */
async function refreshScanList(): Promise<void> {
    try {
        const { scans } = await getScans();

        const container = document.getElementById('scan-selector-container');
        const selector = document.getElementById('scan-selector') as HTMLSelectElement;
        const scanList = document.getElementById('scan-list');

        if (scans.length === 0) {
            if (container) container.style.display = 'none';
            if (scanList) scanList.innerHTML = '';
            return;
        }

        // Show selector
        if (container) container.style.display = 'block';

        // Populate selector dropdown
        if (selector) {
            selector.innerHTML = '<option value="all">All Scans (' + scans.length + ')</option>' +
                scans.map(s =>
                    `<option value="${s.id}">${escapeHtml(s.name)} (${s.vuln_count} vulns)</option>`
                ).join('');
        }

        // Populate scan list with delete buttons
        if (scanList) {
            scanList.innerHTML = scans.map(s => `
                <div class="scan-item" data-id="${s.id}">
                    <span class="scan-name" title="${escapeHtml(s.filename)}">${escapeHtml(s.name)}</span>
                    <span class="scan-vulns">${s.vuln_count} vulns</span>
                    <button class="scan-delete" onclick="deleteScanItem('${s.id}')" title="Delete scan">🗑️</button>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('Failed to refresh scan list:', error);
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text: string): string {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Refresh data status display
 */
async function refreshDataStatus(): Promise<void> {
    try {
        const status = await getDataStatus();

        const dataSourceEl = document.getElementById('data-source');
        const trivyCountEl = document.getElementById('trivy-count');

        if (dataSourceEl) dataSourceEl.textContent = status.current_source;
        if (trivyCountEl) trivyCountEl.textContent = String(status.trivy_uploads);

        // Enable rebuild button if there are uploads
        if (status.trivy_uploads > 0) {
            enableRebuildButton();
        } else {
            disableRebuildButton();
        }
    } catch (error) {
        console.error('Failed to refresh data status:', error);
    }
}

/**
 * Set status message
 */
function setStatus(message: string, type: 'pending' | 'success' | 'error'): void {
    const statusEl = document.getElementById('upload-status');
    if (!statusEl) return;

    statusEl.textContent = message;

    // Set color based on type
    switch (type) {
        case 'pending':
            statusEl.style.color = '#f0ad4e';
            break;
        case 'success':
            statusEl.style.color = '#5cb85c';
            break;
        case 'error':
            statusEl.style.color = '#d9534f';
            break;
    }
}

/**
 * Enable the rebuild button
 */
function enableRebuildButton(): void {
    const btn = document.getElementById('rebuild-btn') as HTMLButtonElement;
    if (btn) btn.disabled = false;
}

/**
 * Disable the rebuild button
 */
function disableRebuildButton(): void {
    const btn = document.getElementById('rebuild-btn') as HTMLButtonElement;
    if (btn) btn.disabled = true;
}
