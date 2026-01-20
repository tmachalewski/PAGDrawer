/**
 * Node search functionality
 * Allows users to find and highlight nodes by their label text
 */

import { getCy } from '../graph/core';

let searchInput: HTMLInputElement | null = null;
let clearButton: HTMLButtonElement | null = null;
let matchCountDisplay: HTMLSpanElement | null = null;
let debounceTimer: number | null = null;

const DEBOUNCE_MS = 200;
const MIN_QUERY_LENGTH = 2;

/**
 * Setup search input and event handlers
 */
export function setupSearch(): void {
    searchInput = document.getElementById('node-search') as HTMLInputElement;
    clearButton = document.getElementById('search-clear') as HTMLButtonElement;
    matchCountDisplay = document.getElementById('search-match-count') as HTMLSpanElement;

    if (!searchInput) {
        console.warn('Search input not found');
        return;
    }

    // Input event with debounce
    searchInput.addEventListener('input', () => {
        if (debounceTimer) {
            clearTimeout(debounceTimer);
        }
        debounceTimer = window.setTimeout(() => {
            const query = searchInput?.value.trim() || '';
            if (query.length >= MIN_QUERY_LENGTH) {
                const matchCount = performSearch(query);
                updateMatchCount(matchCount);
                showClearButton(true);
            } else if (query.length === 0) {
                clearSearch();
            } else {
                // Query too short - clear highlighting but keep input
                clearHighlighting();
                updateMatchCount(0);
                showClearButton(query.length > 0);
            }
        }, DEBOUNCE_MS);
    });

    // Keyboard shortcuts
    searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            clearSearch();
            searchInput?.blur();
        } else if (e.key === 'Enter') {
            // Fit view to matches
            fitToMatches();
        }
    });

    // Clear button click
    if (clearButton) {
        clearButton.addEventListener('click', () => {
            clearSearch();
            searchInput?.focus();
        });
    }

    // Global keyboard shortcut: Ctrl+F or / to focus search
    document.addEventListener('keydown', (e) => {
        // Skip if user is typing in an input/textarea
        if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
            return;
        }

        if (e.key === '/' || (e.ctrlKey && e.key === 'f')) {
            e.preventDefault();
            focusSearch();
        }
    });
}

/**
 * Perform search and highlight matching nodes
 * @param query - Search query string
 * @returns Number of matching nodes
 */
export function performSearch(query: string): number {
    const cy = getCy();
    if (!cy) return 0;

    const lowerQuery = query.toLowerCase();

    // Clear previous search state
    cy.elements().removeClass('search-match search-dimmed');

    // Find matching nodes (case-insensitive, partial match on label)
    const matchingNodes = cy.nodes().filter(node => {
        const label = (node.data('label') || node.data('id') || '').toLowerCase();
        return label.includes(lowerQuery);
    });

    if (matchingNodes.length > 0) {
        // Highlight matching nodes
        matchingNodes.addClass('search-match');

        // Dim non-matching nodes and edges
        cy.elements().not(matchingNodes).not(matchingNodes.connectedEdges()).addClass('search-dimmed');

        // Select matching nodes for visibility
        cy.elements().unselect();
        matchingNodes.select();
    } else {
        // No matches - dim everything slightly to indicate "no results"
        cy.elements().addClass('search-dimmed');
    }

    return matchingNodes.length;
}

/**
 * Clear search and restore normal view
 */
export function clearSearch(): void {
    if (searchInput) {
        searchInput.value = '';
    }
    clearHighlighting();
    updateMatchCount(0);
    showClearButton(false);
}

/**
 * Clear just the highlighting without clearing the input
 */
function clearHighlighting(): void {
    const cy = getCy();
    if (!cy) return;

    cy.elements().removeClass('search-match search-dimmed');
    cy.elements().unselect();
}

/**
 * Focus the search input
 */
export function focusSearch(): void {
    if (searchInput) {
        searchInput.focus();
        searchInput.select();
    }
}

/**
 * Fit view to show matching nodes
 */
function fitToMatches(): void {
    const cy = getCy();
    if (!cy) return;

    const matches = cy.nodes('.search-match');
    if (matches.length > 0) {
        cy.fit(matches, 50);
    }
}

/**
 * Update the match count display
 */
function updateMatchCount(count: number): void {
    if (matchCountDisplay) {
        if (count > 0) {
            matchCountDisplay.textContent = `${count} match${count !== 1 ? 'es' : ''}`;
            matchCountDisplay.style.display = 'inline';
        } else if (searchInput?.value && searchInput.value.length >= MIN_QUERY_LENGTH) {
            matchCountDisplay.textContent = 'No matches';
            matchCountDisplay.style.display = 'inline';
        } else {
            matchCountDisplay.style.display = 'none';
        }
    }
}

/**
 * Show/hide the clear button
 */
function showClearButton(show: boolean): void {
    if (clearButton) {
        clearButton.style.display = show ? 'flex' : 'none';
    }
}
