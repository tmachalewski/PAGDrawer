/**
 * API service for communicating with the backend
 */

import type { GraphData, Stats } from '../types';

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
