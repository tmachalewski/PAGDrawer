/**
 * Unit tests for cveMerge module
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock dependencies
vi.mock('../graph/core', () => ({
    getCy: vi.fn()
}));

vi.mock('../graph/layout', () => ({
    runLayout: vi.fn()
}));

import { getCy } from '../graph/core';
import {
    isMergeAvailable,
    computePrereqKey,
    computeOutcomeKey,
    formatMergeLabel,
    getMergeMode,
    setMergeMode,
    applyMerge,
    removeMerge,
    resetMerge,
    injectGetHiddenTypes,
} from './cveMerge';

const mockedGetCy = vi.mocked(getCy);

// Mock hidden types via injection (no circular import)
let mockHiddenTypes = new Set<string>();
const mockedGetHiddenTypes = () => mockHiddenTypes;

describe('cveMerge', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockHiddenTypes = new Set();
        // Inject mock hidden types
        injectGetHiddenTypes(mockedGetHiddenTypes);
        // Reset merge state
        resetMerge();
        // Setup minimal DOM for button/popover
        document.body.innerHTML = `
            <button class="merge-toggle disabled" id="cve-merge-btn" disabled></button>
            <div id="merge-popover" style="display: none;">
                <div class="merge-option active" data-mode="none">No Merge</div>
                <div class="merge-option" data-mode="prereqs">By Prerequisites</div>
                <div class="merge-option" data-mode="outcomes">By Outcomes</div>
            </div>
        `;
    });

    describe('isMergeAvailable', () => {
        it('returns false when nothing is hidden', () => {
            mockHiddenTypes = new Set();
            expect(isMergeAvailable()).toBe(false);
        });

        it('returns false when only CWE is hidden', () => {
            mockHiddenTypes = new Set(['CWE']);
            expect(isMergeAvailable()).toBe(false);
        });

        it('returns false when only TI is hidden', () => {
            mockHiddenTypes = new Set(['TI']);
            expect(isMergeAvailable()).toBe(false);
        });

        it('returns true when both CWE and TI are hidden', () => {
            mockHiddenTypes = new Set(['CWE', 'TI']);
            expect(isMergeAvailable()).toBe(true);
        });

        it('returns true when CWE, TI, and VC are all hidden', () => {
            mockHiddenTypes = new Set(['CWE', 'TI', 'VC']);
            expect(isMergeAvailable()).toBe(true);
        });

        it('returns false when CWE and CPE are hidden but not TI', () => {
            mockHiddenTypes = new Set(['CWE', 'CPE']);
            expect(isMergeAvailable()).toBe(false);
        });
    });

    describe('computePrereqKey', () => {
        function makeNode(prereqs: Record<string, string> | null, depth: number = 0, layer: string = 'L1'): any {
            return {
                data: (key: string) => {
                    if (key === 'prereqs') return prereqs;
                    if (key === 'chain_depth') return depth;
                    if (key === 'layer') return layer;
                    return undefined;
                }
            };
        }

        it('creates key from prereqs dict on node data', () => {
            const node = makeNode({ AV: 'N', AC: 'L', PR: 'N', UI: 'N' });
            expect(computePrereqKey(node)).toBe('AV:N|AC:L|PR:N|UI:N|L1|d0');
        });

        it('includes chain_depth in key', () => {
            const node = makeNode({ AV: 'L', AC: 'L', PR: 'L', UI: 'N' }, 1);
            expect(computePrereqKey(node)).toBe('AV:L|AC:L|PR:L|UI:N|L1|d1');
        });

        it('returns "unknown" for nodes without prereqs', () => {
            const node = makeNode(null, 0);
            expect(computePrereqKey(node)).toBe('unknown|L1|d0');
        });

        it('groups nodes with identical prereqs under same key', () => {
            const node1 = makeNode({ AV: 'N', AC: 'L', PR: 'N', UI: 'N' });
            const node2 = makeNode({ AV: 'N', AC: 'L', PR: 'N', UI: 'N' });
            expect(computePrereqKey(node1)).toBe(computePrereqKey(node2));
        });

        it('separates nodes at different depths', () => {
            const node1 = makeNode({ AV: 'N', AC: 'L', PR: 'N', UI: 'N' }, 0);
            const node2 = makeNode({ AV: 'N', AC: 'L', PR: 'N', UI: 'N' }, 1);
            expect(computePrereqKey(node1)).not.toBe(computePrereqKey(node2));
        });

        it('separates nodes with different prereqs', () => {
            const node1 = makeNode({ AV: 'N', AC: 'L', PR: 'N', UI: 'N' });
            const node2 = makeNode({ AV: 'L', AC: 'L', PR: 'H', UI: 'N' });
            expect(computePrereqKey(node1)).not.toBe(computePrereqKey(node2));
        });

        it('separates nodes in different layers', () => {
            const node1 = makeNode({ AV: 'N', AC: 'L', PR: 'N', UI: 'N' }, 0, 'L1');
            const node2 = makeNode({ AV: 'N', AC: 'L', PR: 'N', UI: 'N' }, 0, 'L2');
            expect(computePrereqKey(node1)).not.toBe(computePrereqKey(node2));
        });
    });

    describe('computeOutcomeKey', () => {
        function makeNode(outcomes: [string, string][] | null, depth: number = 0, layer: string = 'L1'): any {
            return {
                data: (key: string) => {
                    if (key === 'vc_outcomes') return outcomes;
                    if (key === 'chain_depth') return depth;
                    if (key === 'layer') return layer;
                    return undefined;
                }
            };
        }

        it('creates key from vc_outcomes array on node data', () => {
            const node = makeNode([['AV', 'L'], ['EX', 'Y'], ['PR', 'H']]);
            expect(computeOutcomeKey(node)).toBe('AV:L,EX:Y,PR:H|L1|d0');
        });

        it('includes chain_depth in key', () => {
            const node = makeNode([['AV', 'L']], 2);
            expect(computeOutcomeKey(node)).toBe('AV:L|L1|d2');
        });

        it('returns "unknown" for nodes without vc_outcomes', () => {
            const node = makeNode(null, 0);
            expect(computeOutcomeKey(node)).toBe('unknown|L1|d0');
        });

        it('handles empty vc_outcomes (DoS CVEs)', () => {
            const node = makeNode([]);
            expect(computeOutcomeKey(node)).toBe('none|L1|d0');
        });

        it('produces same key for identical outcome sets', () => {
            const node1 = makeNode([['AV', 'L'], ['PR', 'H']]);
            const node2 = makeNode([['AV', 'L'], ['PR', 'H']]);
            expect(computeOutcomeKey(node1)).toBe(computeOutcomeKey(node2));
        });

        it('separates nodes in different layers', () => {
            const node1 = makeNode([['AV', 'L']], 0, 'L1');
            const node2 = makeNode([['AV', 'L']], 0, 'L2');
            expect(computeOutcomeKey(node1)).not.toBe(computeOutcomeKey(node2));
        });
    });

    describe('formatMergeLabel', () => {
        it('formats prereq key with slash separator', () => {
            const label = formatMergeLabel('AV:N|AC:L|PR:N|UI:N|L1|d0', 6, 'prereqs');
            expect(label).toBe('AV:N / AC:L / PR:N / UI:N (×6)');
        });

        it('formats outcome key with arrow prefix', () => {
            const label = formatMergeLabel('AV:L,EX:Y,PR:H|L1|d0', 3, 'outcomes');
            expect(label).toBe('→ AV:L, EX:Y, PR:H (×3)');
        });

        it('strips layer and depth suffix from display', () => {
            const label = formatMergeLabel('AV:N|AC:L|PR:N|UI:N|L2|d2', 4, 'prereqs');
            expect(label).not.toContain('d2');
            expect(label).not.toContain('L2');
            expect(label).toBe('AV:N / AC:L / PR:N / UI:N (×4)');
        });

        it('handles empty outcomes label', () => {
            const label = formatMergeLabel('none|L1|d0', 2, 'outcomes');
            expect(label).toBe('→ no VCs (×2)');
        });
    });

    describe('getMergeMode', () => {
        it('returns none by default', () => {
            expect(getMergeMode()).toBe('none');
        });
    });

    describe('setMergeMode', () => {
        it('updates merge mode', () => {
            mockedGetCy.mockReturnValue(null as any);
            setMergeMode('prereqs');
            expect(getMergeMode()).toBe('prereqs');
        });

        it('updates button active class for active mode', () => {
            mockedGetCy.mockReturnValue(null as any);
            setMergeMode('prereqs');
            const btn = document.getElementById('cve-merge-btn');
            expect(btn?.classList.contains('active')).toBe(true);
        });

        it('removes button active class for none mode', () => {
            mockedGetCy.mockReturnValue(null as any);
            setMergeMode('prereqs');
            setMergeMode('none');
            const btn = document.getElementById('cve-merge-btn');
            expect(btn?.classList.contains('active')).toBe(false);
        });

        it('updates popover active option', () => {
            mockedGetCy.mockReturnValue(null as any);
            setMergeMode('outcomes');
            const activeOptions = document.querySelectorAll('.merge-option.active');
            expect(activeOptions.length).toBe(1);
            expect((activeOptions[0] as HTMLElement).dataset.mode).toBe('outcomes');
        });
    });

    describe('applyMerge / removeMerge', () => {
        function makeMockCy(
            cveNodes: { id: string; prereqs: any; vc_outcomes: any; chain_depth: number }[],
            edges: { id: string; source: string; target: string; type: string }[] = []
        ) {
            const addedNodes: any[] = [];
            const movedParents: Map<string, string | null> = new Map();
            const hiddenEdgeIds = new Set<string>();

            const edgeObjects = edges.map(e => ({
                id: () => e.id,
                source: () => ({ id: () => e.source }),
                target: () => ({ id: () => e.target }),
                data: (key: string) => {
                    if (key === 'type') return e.type;
                    return undefined;
                },
                style: (prop: string, val?: string) => {
                    if (val === 'none') hiddenEdgeIds.add(e.id);
                    if (val === 'element') hiddenEdgeIds.delete(e.id);
                }
            }));

            const nodeObjects = cveNodes.map(n => {
                const nodeEdges = edgeObjects.filter(e =>
                    e.source().id() === n.id || e.target().id() === n.id
                );
                return {
                    id: () => n.id,
                    data: (key: string) => {
                        if (key === 'prereqs') return n.prereqs;
                        if (key === 'vc_outcomes') return n.vc_outcomes;
                        if (key === 'chain_depth') return n.chain_depth;
                        if (key === 'type') return 'CVE';
                        return undefined;
                    },
                    hasClass: (_cls: string) => false,
                    move: ({ parent }: { parent: string | null }) => {
                        movedParents.set(n.id, parent);
                    },
                    connectedEdges: () => ({
                        forEach: (cb: Function) => nodeEdges.forEach(cb)
                    })
                };
            });

            // Build a minimal collection object with forEach + filter that
            // returns another collection so applyMerge's chain works.
            function makeCollection(items: any[]): any {
                return {
                    forEach: (cb: Function) => items.forEach(cb),
                    filter: (pred: (n: any) => boolean) => makeCollection(items.filter(pred)),
                };
            }

            return {
                nodes: (selector: string) => {
                    if (selector === '[type="CVE"]') {
                        return makeCollection(nodeObjects);
                    }
                    return makeCollection([]);
                },
                add: (data: any) => {
                    addedNodes.push(data);
                },
                getElementById: (id: string) => {
                    const found = nodeObjects.find(n => n.id() === id);
                    if (found) return { length: 1, ...found, children: () => ({ move: () => {} }), remove: () => {} };
                    const addedEdge = edgeObjects.find(e => e.id() === id);
                    if (addedEdge) return { length: 1, ...addedEdge, remove: () => {} };
                    const added = addedNodes.find(n => n.data?.id === id);
                    if (added) return {
                        length: 1,
                        children: () => ({
                            move: ({ parent }: { parent: string | null }) => {
                                cveNodes.forEach(n => movedParents.set(n.id, parent));
                            }
                        }),
                        remove: () => {
                            const idx = addedNodes.findIndex(n => n.data?.id === id);
                            if (idx >= 0) addedNodes.splice(idx, 1);
                        }
                    };
                    return { length: 0 };
                },
                _addedNodes: addedNodes,
                _movedParents: movedParents,
                _hiddenEdgeIds: hiddenEdgeIds
            } as any;
        }

        it('creates compound parent for groups with 2+ CVEs', () => {
            const mockCy = makeMockCy([
                { id: 'cve1', prereqs: { AV: 'N', AC: 'L', PR: 'N', UI: 'N' }, vc_outcomes: [], chain_depth: 0 },
                { id: 'cve2', prereqs: { AV: 'N', AC: 'L', PR: 'N', UI: 'N' }, vc_outcomes: [], chain_depth: 0 },
                { id: 'cve3', prereqs: { AV: 'L', AC: 'L', PR: 'H', UI: 'N' }, vc_outcomes: [], chain_depth: 0 },
            ]);
            mockedGetCy.mockReturnValue(mockCy);

            setMergeMode('prereqs');

            expect(mockCy._addedNodes.length).toBe(1);
            expect(mockCy._addedNodes[0].data.type).toBe('CVE_GROUP');
            expect(mockCy._addedNodes[0].data.label).toContain('×2');
        });

        it('reparents CVE nodes into compound', () => {
            const mockCy = makeMockCy([
                { id: 'cve1', prereqs: { AV: 'N', AC: 'L', PR: 'N', UI: 'N' }, vc_outcomes: [], chain_depth: 0 },
                { id: 'cve2', prereqs: { AV: 'N', AC: 'L', PR: 'N', UI: 'N' }, vc_outcomes: [], chain_depth: 0 },
            ]);
            mockedGetCy.mockReturnValue(mockCy);

            setMergeMode('prereqs');

            expect(mockCy._movedParents.get('cve1')).toContain('cve_merge_prereqs_');
            expect(mockCy._movedParents.get('cve2')).toContain('cve_merge_prereqs_');
        });

        it('does not create compounds for singleton groups', () => {
            const mockCy = makeMockCy([
                { id: 'cve1', prereqs: { AV: 'N', AC: 'L', PR: 'N', UI: 'N' }, vc_outcomes: [], chain_depth: 0 },
                { id: 'cve2', prereqs: { AV: 'L', AC: 'L', PR: 'H', UI: 'N' }, vc_outcomes: [], chain_depth: 0 },
            ]);
            mockedGetCy.mockReturnValue(mockCy);

            setMergeMode('prereqs');

            expect(mockCy._addedNodes.length).toBe(0);
        });

        it('groups by outcomes correctly', () => {
            const mockCy = makeMockCy([
                { id: 'cve1', prereqs: {}, vc_outcomes: [['AV', 'L'], ['PR', 'H']], chain_depth: 0 },
                { id: 'cve2', prereqs: {}, vc_outcomes: [['AV', 'L'], ['PR', 'H']], chain_depth: 0 },
                { id: 'cve3', prereqs: {}, vc_outcomes: [['EX', 'Y']], chain_depth: 0 },
            ]);
            mockedGetCy.mockReturnValue(mockCy);

            setMergeMode('outcomes');

            expect(mockCy._addedNodes.length).toBe(1);
            expect(mockCy._addedNodes[0].data.label).toContain('AV:L');
            expect(mockCy._addedNodes[0].data.label).toContain('×2');
        });

        it('consolidates edges in outcomes mode', () => {
            const mockCy = makeMockCy(
                [
                    { id: 'cve1', prereqs: {}, vc_outcomes: [['AV', 'L']], chain_depth: 0 },
                    { id: 'cve2', prereqs: {}, vc_outcomes: [['AV', 'L']], chain_depth: 0 },
                ],
                [
                    { id: 'e1', source: 'cve1', target: 'vc1', type: 'bridge' },
                    { id: 'e2', source: 'cve2', target: 'vc1', type: 'bridge' },
                    { id: 'e3', source: 'cpe1', target: 'cve1', type: 'has_vuln' },
                    { id: 'e4', source: 'cpe2', target: 'cve2', type: 'has_vuln' },
                ]
            );
            mockedGetCy.mockReturnValue(mockCy);

            setMergeMode('outcomes');

            // Original edges should be hidden
            expect(mockCy._hiddenEdgeIds.size).toBe(4);

            // Synthetic edges: 1 deduped to vc1 + 2 from cpe1/cpe2
            const synEdges = mockCy._addedNodes.filter((e: any) => e.group === 'edges');
            expect(synEdges.length).toBe(3);
            expect(synEdges.every((e: any) => e.data.synthetic)).toBe(true);
        });

        it('does not consolidate edges in prereqs mode', () => {
            const mockCy = makeMockCy(
                [
                    { id: 'cve1', prereqs: { AV: 'N', AC: 'L', PR: 'N', UI: 'N' }, vc_outcomes: [], chain_depth: 0 },
                    { id: 'cve2', prereqs: { AV: 'N', AC: 'L', PR: 'N', UI: 'N' }, vc_outcomes: [], chain_depth: 0 },
                ],
                [
                    { id: 'e1', source: 'cpe1', target: 'cve1', type: 'has_vuln' },
                    { id: 'e2', source: 'cpe1', target: 'cve2', type: 'has_vuln' },
                ]
            );
            mockedGetCy.mockReturnValue(mockCy);

            setMergeMode('prereqs');

            // No edges should be hidden or synthetic in prereqs mode
            expect(mockCy._hiddenEdgeIds.size).toBe(0);
            const synEdges = mockCy._addedNodes.filter((e: any) => e.group === 'edges');
            expect(synEdges.length).toBe(0);
        });

        it('removeMerge is safe to call when no merge is active', () => {
            mockedGetCy.mockReturnValue(null as any);
            expect(() => removeMerge()).not.toThrow();
        });

        it('excludes exploit-hidden CVEs from merge groups', () => {
            // Build a mock where one of the same-prereqs CVEs is exploit-hidden.
            const nodes = [
                { id: 'cve1', prereqs: { AV: 'N', AC: 'L', PR: 'N', UI: 'N' }, vc_outcomes: [], chain_depth: 0 },
                { id: 'cve2', prereqs: { AV: 'N', AC: 'L', PR: 'N', UI: 'N' }, vc_outcomes: [], chain_depth: 0 },
                { id: 'cve3', prereqs: { AV: 'N', AC: 'L', PR: 'N', UI: 'N' }, vc_outcomes: [], chain_depth: 0 },
            ];
            const mockCy = makeMockCy(nodes);
            // Mark cve3 as exploit-hidden by overriding its hasClass
            // via the _addedNodes / node objects accessor: simplest way
            // is to patch the node object directly.
            mockedGetCy.mockReturnValue(mockCy);
            const cveCollection = mockCy.nodes('[type="CVE"]');
            cveCollection.forEach((n: any) => {
                if (n.id() === 'cve3') {
                    n.hasClass = (cls: string) => cls === 'exploit-hidden';
                }
            });

            setMergeMode('prereqs');

            // Only cve1 + cve2 should form a group (2 members, not 3)
            const groupNodes = mockCy._addedNodes.filter((e: any) => e.data?.type === 'CVE_GROUP');
            expect(groupNodes.length).toBe(1);
            expect(groupNodes[0].data.label).toContain('×2');
        });
    });

    describe('resetMerge', () => {
        it('resets mode to none and removes active class', () => {
            mockedGetCy.mockReturnValue(null as any);
            setMergeMode('prereqs');
            resetMerge();
            expect(getMergeMode()).toBe('none');
            const btn = document.getElementById('cve-merge-btn');
            expect(btn?.classList.contains('active')).toBe(false);
        });
    });
});
