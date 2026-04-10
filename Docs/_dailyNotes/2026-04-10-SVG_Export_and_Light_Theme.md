# 2026-04-10 - SVG Export & Light Theme

## Overview

Added two new features for exporting graph visualizations for academic papers:
1. **SVG export** of selected nodes (or full visible graph)
2. **Light theme** toggle for print-friendly, white-background images

---

## 1. SVG Export

**Purpose**: Export parts of the attack graph as SVG for inclusion in academic papers.

**How it works**:
- Select nodes in the graph, then click "Export SVG" in the toolbar
- Exports selected nodes and edges where both source and target are selected
- If nothing is selected, exports the entire visible graph
- Temporarily hides non-exported elements using `.export-hidden` Cytoscape class, generates SVG, then restores

**Implementation**:
- Uses `cytoscape-svg` npm extension (v0.4.0) which renders via `canvas2svg`
- Extension registered lazily on first export via `ensureExtension()`
- SVG generated with `cy.svg({ full: true, scale: 2, bg })` where `bg` adapts to active theme
- Downloaded as blob with descriptive filename: `pagdrawer-{scope}-{timestamp}.svg`

### Files Created/Changed
- `frontend/js/features/exportSvg.ts` (new) - Core export logic
- `frontend/js/config/constants.ts` - Added `.export-hidden` Cytoscape style
- `frontend/js/main.ts` - Import and expose `exportSelectedSvg`
- `frontend/index.html` - Added "Export SVG" toolbar button
- `frontend/package.json` - Added `cytoscape-svg` dependency

---

## 2. Light Theme

**Purpose**: White-background theme for clean, print-ready graph images suitable for academic papers.

**How it works**:
- Click "Light" / "Dark" toggle button in the toolbar
- Switches both the HTML/CSS UI and Cytoscape node/edge styles
- SVG export automatically uses white background in light mode

**Implementation**:
- CSS: `.light-theme` class on `<body>` overrides all UI elements (sidebar, controls, modals, tooltips, etc.)
- Cytoscape: Runtime style overrides applied per-node and per-edge via `node.style()` / `edge.style()`
- Light node colors are darker/more saturated for contrast on white background
- Light text uses dark color (`#111111`) with thin white outline (width: 1) instead of white text with dark outline (width: 2)

### Light Theme Color Mapping

| Node Type | Dark Theme | Light Theme |
|-----------|-----------|-------------|
| HOST      | #ef4444   | #cc2222     |
| CPE       | #f97316   | #cc6600     |
| CVE       | #eab308   | #b8860b     |
| CWE       | #22c55e   | #1a8a1a     |
| TI        | #00bfff   | #0077aa     |
| VC        | #6366f1   | #4a44cc     |
| ATTACKER  | #ff0066   | #cc0055     |

### Files Created/Changed
- `frontend/js/features/theme.ts` (new) - Theme state, color maps, toggle logic
- `frontend/css/styles.css` - Added ~220 lines of `.light-theme` CSS overrides
- `frontend/js/main.ts` - Import and expose `toggleTheme`
- `frontend/index.html` - Added theme toggle toolbar button
- `frontend/js/features/exportSvg.ts` - Adapt SVG background to active theme

---

## Git Commits

```
46b64ee feat: Add SVG export for selected graph elements
2e1a8a4 feat: Add light theme toggle for print-friendly graph exports
```

---

## Summary

| Area | Changes |
|------|---------|
| New features | 2 (SVG export, light theme toggle) |
| New files | 2 (exportSvg.ts, theme.ts) |
| Modified files | 4 (constants.ts, main.ts, index.html, styles.css) |
| New dependency | cytoscape-svg v0.4.0 |
| Test count | Unchanged (406 Python + 82 TypeScript = 488 total) |
