/// <reference types="vitest" />
import { defineConfig } from 'vitest/config';

export default defineConfig({
    root: '.',
    base: '/',
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
