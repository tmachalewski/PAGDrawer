/**
 * Build-time identification injected by `vite.config.ts`.
 *
 * `gitSha` is the full HEAD SHA at build time (or "unknown" if the build
 * happened outside a git checkout). `appVersion` is `frontend/package.json`'s
 * version field at build time.
 *
 * Both are stamped into the metrics JSON export so a downloaded snapshot
 * is traceable back to the exact commit that produced it.
 */

declare const __VITE_GIT_SHA__: string | undefined;
declare const __VITE_APP_VERSION__: string | undefined;

function readEnv(key: string): string {
    // import.meta.env values are replaced at build time by vite's `define`.
    // In tests, vitest applies the same `define` so values are present.
    // Falls back to "unknown" if anything is missing (e.g. ts-node usage).
    const value = (import.meta as any)?.env?.[key];
    return typeof value === 'string' && value.length > 0 ? value : 'unknown';
}

export function getGitSha(): string {
    return readEnv('VITE_GIT_SHA');
}

export function getAppVersion(): string {
    return readEnv('VITE_APP_VERSION');
}
