/**
 * Graph event handlers
 */

import { hideSelectedNodes } from '../features/hideRestore';

/**
 * Setup all event handlers for the graph
 */
export function setupEventHandlers(): void {
    // Keyboard shortcuts only - tap handlers moved to tooltip.ts for unified selection management
    document.addEventListener('keydown', handleKeyboard);
}

/**
 * Handle keyboard shortcuts
 */
function handleKeyboard(e: KeyboardEvent): void {
    if (e.key === 'h' || e.key === 'H') {
        const activeElement = document.activeElement as HTMLElement;
        if (activeElement.tagName !== 'INPUT' && activeElement.tagName !== 'SELECT') {
            hideSelectedNodes();
        }
    }
}
