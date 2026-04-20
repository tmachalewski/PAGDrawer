/**
 * Settings modal functionality
 */

import { updateConfig, fetchGraph, fetchStats } from '../services/api';
import { reapplyHiddenTypes } from '../features/filter';
import { clearHiddenElements } from '../features/hideRestore';
import { initCytoscape, destroyCytoscape } from '../graph/core';
import { runLayout } from '../graph/layout';
import { setupEventHandlers } from '../graph/events';
import { applyEnvironmentFilter } from '../features/environment';
import { updateStats, updateLiveStats, hideLoading } from './sidebar';
import { setupTooltip, clearSelectedNode } from './tooltip';
import { resetMerge } from '../features/cveMerge';

// Node types and their grouping options (chain from ATTACKER to parent)
const SLIDER_OPTIONS: Record<string, string[]> = {
    CPE: ['ATTACKER', 'HOST'],
    CVE: ['ATTACKER', 'HOST', 'CPE'],
    CWE: ['ATTACKER', 'HOST', 'CPE', 'CVE'],
    TI: ['ATTACKER', 'HOST', 'CPE', 'CVE', 'CWE'],
    VC: ['ATTACKER', 'HOST', 'CPE', 'CVE', 'CWE', 'TI']
};

const NODE_TYPES = Object.keys(SLIDER_OPTIONS);

/**
 * Update the slider option labels to highlight the selected one
 */
function updateSliderLabels(type: string, value: number): void {
    const row = document.querySelector(`.node-slider-row[data-type="${type}"]`);
    if (!row) return;

    const options = row.querySelectorAll('.slider-options span');
    options.forEach((opt, index) => {
        opt.classList.remove('active', 'universal-active');
        if (index === value) {
            // Position 0 (ATTACKER) = universal, others = singular/granular
            opt.classList.add(value === 0 ? 'universal-active' : 'active');
        }
    });
}

/**
 * Setup slider change listeners
 */
function setupSliderListeners(): void {
    NODE_TYPES.forEach(type => {
        const slider = document.getElementById(`config-${type}`) as HTMLInputElement | null;
        if (slider) {
            slider.oninput = () => {
                updateSliderLabels(type, parseInt(slider.value, 10));
            };
        }
    });
}

/**
 * Convert backend config value to slider position
 * 'singular' maps to max position (most granular)
 * 'universal' or 'ATTACKER' maps to position 0
 */
function configToSliderPosition(type: string, configValue: string): number {
    const options = SLIDER_OPTIONS[type];
    if (!options) return 0;

    // Handle legacy 'universal' value
    if (configValue === 'universal' || configValue === 'ATTACKER') {
        return 0;
    }

    // Check if configValue matches any option
    const index = options.indexOf(configValue);
    if (index >= 0) return index;

    // Handle legacy 'singular' - map to most granular
    if (configValue === 'singular') {
        return options.length - 1;
    }

    // Default to most granular
    return options.length - 1;
}

/**
 * Convert slider position to config value
 * Returns the actual grouping level (e.g., "ATTACKER", "HOST", "CPE")
 */
function sliderPositionToConfig(type: string, position: number): string {
    const options = SLIDER_OPTIONS[type];
    if (!options || position < 0 || position >= options.length) {
        return 'ATTACKER';
    }
    return options[position];
}

/**
 * Sync slider positions from backend config (without opening modal)
 */
export async function syncSlidersFromConfig(): Promise<void> {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();

        NODE_TYPES.forEach(type => {
            const slider = document.getElementById(`config-${type}`) as HTMLInputElement | null;
            if (slider) {
                const position = configToSliderPosition(type, config[type] || 'singular');
                slider.value = String(position);
                updateSliderLabels(type, position);
            }
        });
    } catch (error) {
        console.error('Error syncing sliders from config:', error);
    }
}

/**
 * Open settings modal and load current config
 */
export async function openSettings(): Promise<void> {
    const modal = document.getElementById('settings-modal');
    if (modal) modal.style.display = 'flex';

    try {
        const response = await fetch('/api/config');
        const config = await response.json();

        // Set each slider based on config
        NODE_TYPES.forEach(type => {
            const slider = document.getElementById(`config-${type}`) as HTMLInputElement | null;
            if (slider) {
                const position = configToSliderPosition(type, config[type] || 'singular');
                slider.value = String(position);
                updateSliderLabels(type, position);
            }
        });

        // Set skip_layer_2 checkbox
        const skipL2 = document.getElementById('config-skip-layer-2') as HTMLInputElement | null;
        if (skipL2) skipL2.checked = !!config.skip_layer_2;
    } catch (error) {
        console.error('Error loading config:', error);
    }

    // Update stats to show current live graph state
    updateLiveStats();

    // Setup listeners
    setupSliderListeners();
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
    // Read each slider position and convert to config value
    const config: Record<string, unknown> = { HOST: 'universal' };
    NODE_TYPES.forEach(type => {
        const slider = document.getElementById(`config-${type}`) as HTMLInputElement | null;
        const position = slider ? parseInt(slider.value, 10) : SLIDER_OPTIONS[type].length - 1;
        config[type] = sliderPositionToConfig(type, position);
    });

    // Read skip_layer_2 checkbox
    const skipL2 = document.getElementById('config-skip-layer-2') as HTMLInputElement | null;
    config.skip_layer_2 = !!skipL2?.checked;

    try {
        // Update config on server
        await updateConfig(config);

        // Reload graph with new config
        const [graphData, stats] = await Promise.all([
            fetchGraph(),
            fetchStats()
        ]);

        // Clear tooltip, hidden state, and merge before destroying old graph
        clearSelectedNode();
        clearHiddenElements();
        resetMerge();

        // Reinitialize Cytoscape
        destroyCytoscape();
        initCytoscape(graphData.elements);
        setupEventHandlers();
        setupTooltip();

        // Reapply hidden types from before rebuild
        reapplyHiddenTypes();

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
