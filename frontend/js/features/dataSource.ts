/**
 * Data Source Management Feature
 * Handles Trivy file uploads and graph rebuilding from the UI
 */

import { uploadTrivyFile, rebuildData, resetData, getDataStatus, fetchGraph, fetchStats } from '../services/api';
import { initCytoscape } from '../graph/core';
import { runLayout } from '../graph/layout';
import { updateStats } from '../ui/sidebar';

/**
 * Initialize data source panel - fetch and display current status
 */
export function initDataSource(): void {
    refreshDataStatus();
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
        setStatus(`✅ Uploaded: ${file.name}`, 'success');
        enableRebuildButton();
        refreshDataStatus();
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
 * Rebuild graph from uploaded data
 */
export async function rebuildGraph(): Promise<void> {
    const enrichCheckbox = document.getElementById('enrich-checkbox') as HTMLInputElement;
    const enrich = enrichCheckbox?.checked ?? true;

    const statusMsg = enrich
        ? 'Rebuilding with enrichment (may take a minute)...'
        : 'Rebuilding...';
    setStatus(statusMsg, 'pending');
    disableRebuildButton();

    try {
        await rebuildData(enrich);

        // Reload graph with new data
        const [graphData, stats] = await Promise.all([fetchGraph(), fetchStats()]);
        initCytoscape(graphData.elements);
        setTimeout(() => runLayout(), 100);
        updateStats(stats);

        setStatus('✅ Graph rebuilt successfully', 'success');
        refreshDataStatus();
        console.log('Graph rebuilt with enrich=' + enrich);
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
        initCytoscape(graphData.elements);
        setTimeout(() => runLayout(), 100);
        updateStats(stats);

        setStatus('✅ Reset to mock data', 'success');
        refreshDataStatus();
        disableRebuildButton();
        console.log('Reset to mock data');
    } catch (error) {
        const message = error instanceof Error ? error.message : 'Reset failed';
        setStatus(`❌ ${message}`, 'error');
        console.error('Reset error:', error);
    }
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
