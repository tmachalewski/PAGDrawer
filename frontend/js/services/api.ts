/**
 * API service for communicating with the backend
 */

import type { GraphData, Stats, UploadResponse, RebuildResponse, DataStatus, ScansResponse } from '../types';

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
 * Start a rebuild job. Returns immediately with { status: "started", job_id }.
 * Poll fetchRebuildProgress(job_id) to track completion.
 */
export async function startRebuild(
    enrich: boolean = true,
    scanIds?: string[],
    forceRefresh: boolean = false
): Promise<{ status: string; job_id: string }> {
    const params = new URLSearchParams({
        enrich: String(enrich),
        use_deployment: 'false',
        force_refresh: String(forceRefresh),
    });

    if (scanIds && scanIds.length > 0) {
        scanIds.forEach(id => params.append('scan_ids', id));
    }

    const response = await fetch(
        `${API_BASE}/api/data/rebuild?${params}`,
        { method: 'POST' }
    );
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: `Rebuild failed: ${response.status}` }));
        const detailMsg = typeof error.detail === 'object'
            ? (error.detail.message || JSON.stringify(error.detail))
            : error.detail;
        throw new Error(detailMsg || `Rebuild failed: ${response.status}`);
    }
    return response.json();
}

/**
 * Progress response shape from /api/data/rebuild/progress/{job_id}.
 */
export interface RebuildProgress {
    job_id: string;
    status: 'running' | 'completed' | 'failed' | 'cancelled';
    phase: string;
    current_cve: string | null;
    processed_cves: number;
    total_cves: number;
    error: string | null;
    stats: Record<string, unknown> | null;
    started_at: string;
    completed_at: string | null;
    cancel_requested: boolean;
}

/**
 * Fetch current progress for a rebuild job.
 */
export async function fetchRebuildProgress(jobId: string): Promise<RebuildProgress> {
    const response = await fetch(`${API_BASE}/api/data/rebuild/progress/${jobId}`);
    if (!response.ok) {
        throw new Error(`Progress fetch failed: ${response.status}`);
    }
    return response.json();
}

/**
 * Request cancellation of a running rebuild job.
 */
export async function cancelRebuild(jobId: string): Promise<void> {
    const response = await fetch(
        `${API_BASE}/api/data/rebuild/cancel/${jobId}`,
        { method: 'POST' }
    );
    if (!response.ok) {
        throw new Error(`Cancel failed: ${response.status}`);
    }
}

/**
 * Legacy synchronous rebuild wrapper — kept for backward compatibility.
 * Internally it kicks off a job and polls until completion.
 * Prefer startRebuild + fetchRebuildProgress for UI with a progress bar.
 */
export async function rebuildData(enrich: boolean = true, scanIds?: string[]): Promise<RebuildResponse> {
    const { job_id } = await startRebuild(enrich, scanIds);
    while (true) {
        const progress = await fetchRebuildProgress(job_id);
        if (progress.status === 'completed') {
            return {
                status: 'ok',
                source: (progress.stats?.source as string) ?? 'unknown',
                stats: progress.stats as unknown as Stats,
            };
        }
        if (progress.status === 'failed') {
            throw new Error(progress.error || 'Rebuild failed');
        }
        if (progress.status === 'cancelled') {
            throw new Error('Rebuild cancelled');
        }
        await new Promise(r => setTimeout(r, 500));
    }
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

/**
 * Get list of uploaded scans with metadata
 */
export async function getScans(): Promise<ScansResponse> {
    const response = await fetch(`${API_BASE}/api/data/scans`);
    if (!response.ok) {
        throw new Error(`Failed to get scans: ${response.status}`);
    }
    return response.json();
}

/**
 * Delete a specific scan by ID
 */
export async function deleteScan(scanId: string): Promise<{ status: string; remaining: number }> {
    const response = await fetch(`${API_BASE}/api/data/scans/${scanId}`, {
        method: 'DELETE'
    });
    if (!response.ok) {
        throw new Error(`Failed to delete scan: ${response.status}`);
    }
    return response.json();
}
