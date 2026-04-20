/**
 * Rebuild progress bar — polls /api/data/rebuild/progress/<job_id>
 * and renders a progress bar in the data source panel.
 */

import {
    startRebuild,
    fetchRebuildProgress,
    cancelRebuild,
    type RebuildProgress,
} from '../services/api';

const POLL_INTERVAL_MS = 500;

const PHASE_LABELS: Record<string, string> = {
    loading: 'Parsing Trivy data',
    enriching_nvd: 'Fetching CVE details from NVD',
    enriching_cwe: 'Fetching CWE impacts',
    building_graph: 'Building attack graph',
    done: 'Done',
};

export interface ProgressCallbacks {
    onUpdate?: (progress: RebuildProgress) => void;
    onComplete?: (progress: RebuildProgress) => void;
    onError?: (message: string) => void;
}

/**
 * Start a rebuild and poll until it terminates.
 * Resolves with the final RebuildProgress on success; rejects on failure.
 */
export async function rebuildWithProgress(
    enrich: boolean,
    scanIds?: string[],
    forceRefresh: boolean = false,
    callbacks: ProgressCallbacks = {}
): Promise<RebuildProgress> {
    showProgressBar();

    let jobId: string;
    try {
        const { job_id } = await startRebuild(enrich, scanIds, forceRefresh);
        jobId = job_id;
    } catch (e) {
        hideProgressBar();
        const msg = e instanceof Error ? e.message : String(e);
        callbacks.onError?.(msg);
        throw e;
    }

    setCancelHandler(() => cancelRebuild(jobId).catch(console.error));

    while (true) {
        let progress: RebuildProgress;
        try {
            progress = await fetchRebuildProgress(jobId);
        } catch (e) {
            hideProgressBar();
            const msg = e instanceof Error ? e.message : String(e);
            callbacks.onError?.(msg);
            throw e;
        }

        renderProgress(progress);
        callbacks.onUpdate?.(progress);

        if (progress.status === 'completed') {
            hideProgressBar();
            callbacks.onComplete?.(progress);
            return progress;
        }
        if (progress.status === 'failed') {
            hideProgressBar();
            const msg = progress.error ?? 'Rebuild failed';
            callbacks.onError?.(msg);
            throw new Error(msg);
        }
        if (progress.status === 'cancelled') {
            hideProgressBar();
            callbacks.onError?.('Rebuild cancelled');
            throw new Error('Rebuild cancelled');
        }

        await sleep(POLL_INTERVAL_MS);
    }
}

// -----------------------------------------------------------------------------
// DOM rendering
// -----------------------------------------------------------------------------

function showProgressBar(): void {
    const container = document.getElementById('rebuild-progress');
    if (container) container.style.display = 'block';
    setText('rebuild-progress-phase', 'Starting...');
    setText('rebuild-progress-current', '');
    setText('rebuild-progress-count', '');
    setProgressWidth(0);
}

function hideProgressBar(): void {
    const container = document.getElementById('rebuild-progress');
    if (container) container.style.display = 'none';
}

function renderProgress(p: RebuildProgress): void {
    const phaseLabel = PHASE_LABELS[p.phase] ?? p.phase;
    setText('rebuild-progress-phase', phaseLabel);
    setText('rebuild-progress-current', p.current_cve ? `Current: ${p.current_cve}` : '');

    if (p.total_cves > 0) {
        const pct = Math.min(100, Math.round((p.processed_cves / p.total_cves) * 100));
        setText('rebuild-progress-count', `${p.processed_cves} / ${p.total_cves} CVEs  (${pct}%)`);
        setProgressWidth(pct);
    } else {
        setText('rebuild-progress-count', 'Preparing...');
        setProgressWidth(0);
    }
}

function setProgressWidth(pct: number): void {
    const fill = document.getElementById('rebuild-progress-fill');
    if (fill) fill.style.width = `${pct}%`;
}

function setText(id: string, value: string): void {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function setCancelHandler(handler: () => void): void {
    const btn = document.getElementById('rebuild-progress-cancel') as HTMLButtonElement | null;
    if (!btn) return;
    btn.onclick = handler;
}

function sleep(ms: number): Promise<void> {
    return new Promise(r => setTimeout(r, ms));
}
