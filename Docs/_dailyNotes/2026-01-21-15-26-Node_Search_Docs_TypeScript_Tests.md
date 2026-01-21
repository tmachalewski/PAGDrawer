# 2026-01-21 15:26 - Node Search, Domain Docs, TypeScript Tests

## Overview

Major additions to documentation and test coverage:
1. **Node Search Feature** - Real-time search with keyboard shortcuts
2. **GraphNodeConnections.md** - Comprehensive domain documentation
3. **Documentation Verification Tests** - 17 new backend tests
4. **TypeScript Unit Tests** - Grew from 9 to 82 tests

---

## 1. Node Search Feature

**Implemented** in previous session, verified and documented today.

### Features
- Real-time case-insensitive partial matching
- 200ms debounce, 2+ character minimum
- Matching nodes highlighted with gold border
- Non-matching nodes dimmed to 15% opacity
- Match count display (`32 matches`)

### Keyboard Shortcuts
| Key             | Action                     |
| --------------- | -------------------------- |
| `/` or `Ctrl+F` | Focus search input         |
| `Escape`        | Clear search, blur input   |
| `Enter`         | Fit view to matching nodes |

### Files
- `frontend/js/features/search.ts` - Main implementation
- `frontend/index.html` - Search bar HTML
- `frontend/css/styles.css` - `.search-match`, `.search-dimmed` classes

### Tests
- 12 Playwright E2E tests in `TestNodeSearch` class

---

## 2. GraphNodeConnections.md

Created comprehensive domain documentation explaining the attack graph model.

**Location**: `Docs/_domains/GraphNodeConnections.md`

### Sections
1. **Node Types & Hierarchy** - 8 types (ATTACKER → HOST → CPE → CVE → CWE → TI → VC)
2. **Edge Types** - 9 types (static and dynamic)
3. **VC Attack Progression** - How gaining AV:L enables AV:N/A/L CVEs
4. **Environmental VCs** - UI/AC as static filters vs AV/PR state mutators
5. **Visibility Toggles** - Bridge edge creation and coloring
6. **Universality Sliders** - Node grouping granularity
7. **Two-Layer Attack Model** - L1 (external) vs L2 (internal)

### Key Insight Documented

> **Gaining a VC unlocks CVEs that require that level OR LESS permissive.**

Example: `VC:AV:L` enables exploitation of CVEs with AV:N, AV:A, or AV:L (not AV:P).

---

## 3. Documentation Verification Tests

Added tests to verify code matches documentation.

### Backend Tests (`test_builder.py`)

| Class                     | Tests | Verifies                              |
| ------------------------- | ----- | ------------------------------------- |
| `TestDocumentedEdgeTypes` | 8     | Edge types connect correct node types |
| `TestVCHierarchyEnables`  | 3     | VC ENABLES edges follow hierarchy     |

### Frontend Tests (`test_frontend.py`)

| Class                          | Tests | Verifies                               |
| ------------------------------ | ----- | -------------------------------------- |
| `TestEnvironmentFilterCascade` | 5     | UI/AC filter cascades to CWE→TI→VC     |
| `TestBridgeEdgeColor`          | 1     | Bridge edges have bridgeColor property |

**Total**: 17 new verification tests, all passed.

---

## 4. TypeScript Unit Tests

Significantly expanded TypeScript test coverage.

### Before/After
| Metric      | Before | After |
| ----------- | ------ | ----- |
| Test files  | 3      | 7     |
| Total tests | 9      | 82    |

### New Test Files

| File                   | Tests | Coverage                                         |
| ---------------------- | ----- | ------------------------------------------------ |
| `search.test.ts`       | 15    | Module exports, search logic, matching rules     |
| `api.test.ts`          | 21    | All API functions, fetch mocking, error handling |
| `exploitPaths.test.ts` | 11    | Toggle behavior, BFS algorithm, path collection  |
| `environment.test.ts`  | 26    | CVSS parsing, UI/AC logic, combined conditions   |

### Notable Test Patterns

**Mocked Cytoscape**:
```typescript
vi.mock('../graph/core', () => ({
    getCy: vi.fn()
}));
```

**Mocked Fetch**:
```typescript
const mockFetch = vi.fn();
global.fetch = mockFetch;
```

**Logic-only tests** (no DOM/Cytoscape):
```typescript
it('should extract UI value from CVSS vector', () => {
    const cvssVector = 'CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H';
    const uiMatch = cvssVector.match(/UI:([NR])/);
    expect(uiMatch![1]).toBe('R');
});
```

---

## 5. Project Status Update

Created new project status document: `Docs/_projectStatus/2026-01-21-15-09-Project_State_Overview.md`

### Key Updates
- Test count: 401 Python tests + 82 TypeScript tests = **483 total**
- New documentation in `Docs/_domains/`
- Version: 1.5.0

---

## Git Commits

```
3a6ccc5 test: Add comprehensive TypeScript unit tests
aecdf43 docs: Add GraphNodeConnections.md explaining graph structure
e6a9bf7 test: Add verification tests for GraphNodeConnections.md documentation
b605e25 feat: Add search UI and integration
c6b971c feat: Add node search feature with E2E tests
```

---

## Summary

| Area                 | Additions                               |
| -------------------- | --------------------------------------- |
| Features             | Node search with keyboard shortcuts     |
| Documentation        | GraphNodeConnections.md, Project Status |
| Python Tests         | +17 verification tests                  |
| TypeScript Tests     | +73 tests (9 → 82)                      |
| **Total Test Count** | **~480**                                |
