/// <reference types="vitest" />
import { defineConfig } from 'vitest/config';
import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

/**
 * Build-time constants injected via Vite's `define`.
 *
 * VITE_GIT_SHA — full SHA of HEAD at build time. Used to stamp every metrics
 *   JSON export with the exact code revision that produced it. Falls back to
 *   "unknown" if the build is happening outside a git checkout (e.g. tarball).
 *
 * VITE_APP_VERSION — frontend/package.json's "version" field. Informational,
 *   bumped by hand when the project's marketing version changes.
 *
 * Note: in dev mode the SHA reflects HEAD even if the working tree is dirty.
 * We do not detect dirty state in this iteration (documented in
 * `Docs/Plans/JSON_Export_With_Settings.md` § "Reproducibility").
 */
function readGitSha(): string {
    try {
        return execSync('git rev-parse HEAD', { cwd: __dirname }).toString().trim();
    } catch {
        return 'unknown';
    }
}

function readAppVersion(): string {
    try {
        const pkg = JSON.parse(readFileSync(resolve(__dirname, 'package.json'), 'utf-8'));
        return typeof pkg.version === 'string' ? pkg.version : 'unknown';
    } catch {
        return 'unknown';
    }
}

const gitSha = readGitSha();
const appVersion = readAppVersion();

export default defineConfig({
    root: '.',
    base: '/',
    define: {
        // Plain global identifiers — Vite's `define` does literal text
        // replacement, so the source must reference these exact tokens.
        // See `frontend/js/config/buildInfo.ts`.
        __GIT_SHA__: JSON.stringify(gitSha),
        __APP_VERSION__: JSON.stringify(appVersion),
    },
    build: {
        outDir: 'dist',
        emptyOutDir: true,
        sourcemap: true,
    },
    server: {
        port: 3000,
        proxy: {
            // Proxy API endpoints to FastAPI backend
            '/api': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
        },
    },
    test: {
        globals: true,
        environment: 'jsdom',
        include: ['js/**/*.test.ts'],
        coverage: {
            provider: 'v8',
            reporter: ['text', 'html'],
            include: ['js/**/*.ts'],
            exclude: ['js/**/*.test.ts', 'js/main.ts'],
        },
    },
});
