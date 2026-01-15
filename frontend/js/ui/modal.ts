/**
 * Settings modal functionality
 */

import { updateConfig, fetchGraph, fetchStats } from '../services/api';
import { initCytoscape, destroyCytoscape } from '../graph/core';
import { runLayout } from '../graph/layout';
import { setupEventHandlers } from '../graph/events';
import { applyEnvironmentFilter } from '../features/environment';
import { updateStats, hideLoading } from './sidebar';



/**
 * Open settings modal and load current config
 */
export async function openSettings(): Promise<void> {
    const modal = document.getElementById('settings-modal');
    if (modal) modal.style.display = 'flex';

    try {
        const response = await fetch('/api/config');
        const config = await response.json();

        // Set current values in dropdowns
        (['CPE', 'CVE', 'CWE', 'TI', 'VC'] as const).forEach(type => {
            const select = document.getElementById(`config-${type}`) as HTMLSelectElement | null;
            if (select && config[type]) {
                select.value = config[type];
            }
        });
    } catch (error) {
        console.error('Error loading config:', error);
    }
}

/**
 * Close settings modal
 */
export function closeSettings(): void {
    const modal = document.getElementById('settings-modal');
    if (modal) modal.style.display = 'none';
}

/**
 * Save settings and rebuild graph
 */
export async function saveSettings(): Promise<void> {
    const getSelectValue = (id: string): string => {
        const el = document.getElementById(id) as HTMLSelectElement | null;
        return el?.value || '';
    };

    const config = {
        HOST: 'universal',
        CPE: getSelectValue('config-CPE'),
        CVE: getSelectValue('config-CVE'),
        CWE: getSelectValue('config-CWE'),
        TI: getSelectValue('config-TI'),
        VC: getSelectValue('config-VC')
    };

    try {
        // Update config on server
        await updateConfig(config);

        // Reload graph with new config
        const [graphData, stats] = await Promise.all([
            fetchGraph(),
            fetchStats()
        ]);

        // Reinitialize Cytoscape
        destroyCytoscape();
        initCytoscape(graphData.elements);
        setupEventHandlers();

        setTimeout(() => runLayout(), 100);
        hideLoading();
        updateStats(stats);
        applyEnvironmentFilter();

        closeSettings();
    } catch (error) {
        console.error('Error saving settings:', error);
        const err = error as Error;
        alert('Error saving settings: ' + err.message);
    }
}
