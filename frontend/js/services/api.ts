/**
 * API service for communicating with the backend
 */

import type { GraphData, Stats, UploadResponse, RebuildResponse, DataStatus } from '../types';

const API_BASE = '';

/**
 * Fetch graph data from the backend
 */
export async function fetchGraph(): Promise<GraphData> {
    const response = await fetch(`${API_BASE}/api/graph`);
    if (!response.ok) {
        throw new Error(`Failed to fetch graph: ${response.status}`);
    }
    return response.json();
}

/**
 * Fetch graph statistics
 */
export async function fetchStats(): Promise<Stats> {
    const response = await fetch(`${API_BASE}/api/stats`);
    if (!response.ok) {
        throw new Error(`Failed to fetch stats: ${response.status}`);
    }
    return response.json();
}

/**
 * Fetch current configuration
 */
export async function fetchConfig(): Promise<Record<string, unknown>> {
    const response = await fetch(`${API_BASE}/api/config`);
    if (!response.ok) {
        throw new Error(`Failed to fetch config: ${response.status}`);
    }
    return response.json();
}

/**
 * Update configuration and rebuild graph
 */
export async function updateConfig(config: Record<string, unknown>): Promise<{ status: string; stats: Stats }> {
    const response = await fetch(`${API_BASE}/api/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
    });
    if (!response.ok) {
        throw new Error(`Failed to update config: ${response.status}`);
    }
    return response.json();
}

/**
 * Upload a Trivy JSON file
 */
export async function uploadTrivyFile(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE}/api/upload/trivy`, {
        method: 'POST',
        body: formData
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: `Upload failed: ${response.status}` }));
        throw new Error(error.detail || `Upload failed: ${response.status}`);
    }
    return response.json();
}

/**
 * Rebuild graph from uploaded data
 */
export async function rebuildData(enrich: boolean = true): Promise<RebuildResponse> {
    const response = await fetch(
        `${API_BASE}/api/data/rebuild?enrich=${enrich}&use_deployment=false`,
        { method: 'POST' }
    );
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: `Rebuild failed: ${response.status}` }));
        throw new Error(error.detail || `Rebuild failed: ${response.status}`);
    }
    return response.json();
}

/**
 * Reset to mock data
 */
export async function resetData(): Promise<{ status: string; source: string; stats: Stats }> {
    const response = await fetch(`${API_BASE}/api/data/reset`, { method: 'POST' });
    if (!response.ok) {
        throw new Error(`Reset failed: ${response.status}`);
    }
    return response.json();
}

/**
 * Get data source status
 */
export async function getDataStatus(): Promise<DataStatus> {
    const response = await fetch(`${API_BASE}/api/data/status`);
    if (!response.ok) {
        throw new Error(`Failed to get status: ${response.status}`);
    }
    return response.json();
}
