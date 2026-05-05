/**
 * Build-time identification injected by `vite.config.ts` via `define`.
 *
 * `__GIT_SHA__` is the full HEAD SHA at build time (or "unknown" if the
 * build happened outside a git checkout). `__APP_VERSION__` is
 * `frontend/package.json`'s version field at build time.
 *
 * Both are stamped into the metrics JSON export so a downloaded snapshot
 * is traceable back to the exact commit that produced it.
 *
 * Implementation note: Vite's `define` performs literal text replacement
 * during transform. The source MUST reference the exact token configured
 * in `vite.config.ts` (`__GIT_SHA__`, `__APP_VERSION__`) — dynamic access
 * via `(import.meta as any).env[key]` would not be substituted.
 */

declare const __GIT_SHA__: string;
declare const __APP_VERSION__: string;

export function getGitSha(): string {
    try {
        // typeof guard: in environments where the define did not run
        // (e.g. ts-node, plain node), the identifier is undefined.
        return typeof __GIT_SHA__ === 'string' && __GIT_SHA__.length > 0
            ? __GIT_SHA__
            : 'unknown';
    } catch {
        return 'unknown';
    }
}

export function getAppVersion(): string {
    try {
        return typeof __APP_VERSION__ === 'string' && __APP_VERSION__.length > 0
            ? __APP_VERSION__
            : 'unknown';
    } catch {
        return 'unknown';
    }
}
