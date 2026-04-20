# Readability Mechanism: Universality-Singularity Sliders

This document describes how PAGDrawer's granularity sliders improve attack graph readability by controlling node deduplication across the graph.

---

## The Readability Problem

Attack graphs suffer from **combinatorial explosion**. A single vulnerability (e.g., CVE-2021-44228) may affect Apache on 50 hosts. In a fully granular graph, this produces 50 CVE nodes, each with downstream CWE, TI, and VC nodes — potentially hundreds of nodes representing what is conceptually the same exploit path.

At the other extreme, collapsing everything into a single shared CVE node loses the ability to reason about which host is affected.

The challenge: **how much duplication is useful for the analyst's current question?**

---

## The Mechanism: Universality-Singularity Spectrum

Each node type (CPE, CVE, CWE, TI, VC) has a slider that controls its **grouping granularity** — how many copies of that concept exist in the graph.

```
ATTACKER ◄────────────────────────────► Most Granular
(universal/shared)                      (per-instance/singular)
```

### Positions

| Position | Node Identity | Example |
|----------|--------------|---------|
| **ATTACKER** | One globally shared node | `CVE-2021-44228` (one node for all hosts) |
| **HOST** | One per host | `CVE-2021-44228@host-001` |
| **CPE** | One per software instance | `CVE-2021-44228@apache:2.4.41@host-001` |
| **CVE** | One per parent CVE | (only meaningful for CWE and below) |
| **CWE** | One per parent CWE | (only meaningful for TI and below) |
| **TI** | Most granular | Full ancestor context chain |

### Constraints

Each node type can only be grouped by its **ancestors** in the graph hierarchy. A CVE cannot be grouped "per CWE" because CWEs are downstream. This ensures semantic correctness.

| Node | Valid Grouping Levels |
|------|---------------------|
| CPE | ATTACKER, HOST |
| CVE | ATTACKER, HOST, CPE |
| CWE | ATTACKER, HOST, CPE, CVE |
| TI | ATTACKER, HOST, CPE, CVE, CWE |
| VC | ATTACKER, HOST, CPE, CVE, CWE, TI |

---

## How It Aids Readability

### 1. Semantic Zoom

Sliders function as a **semantic zoom** control. Unlike visual zoom (which just scales), semantic zoom changes the *level of detail* in the data:

- **Zoomed out** (universal): "What vulnerabilities exist across my infrastructure?"
- **Zoomed in** (singular): "What is the exact attack path on this specific host?"

This lets analysts match the graph's complexity to their current question without losing data.

### 2. Controlled Node Count

The relationship between slider position and node count is multiplicative. With 5 hosts, 10 CPEs, and 20 CVEs:

| CVE Slider Position | CVE Nodes | Why |
|--------------------|-----------|-----|
| ATTACKER | ~20 | One per unique CVE ID |
| HOST | ~100 | 20 CVEs x 5 hosts (if all affected) |
| CPE | ~200 | 20 CVEs x 10 CPEs (if all affected) |

Downstream nodes (CWE, TI, VC) multiply further. Universal sliders can reduce a 1000-node graph to under 100 nodes.

### 3. Answering Different Questions

| Analyst Question | Recommended Slider Setting |
|-----------------|---------------------------|
| "What weaknesses does my infrastructure have?" | CWE/TI at ATTACKER (shared) |
| "Which host is most vulnerable?" | CVE at HOST, VC at HOST |
| "What exact privilege escalation path exists on host-001?" | All sliders at maximum granularity |
| "Do different hosts share the same exploit outcomes?" | VC at ATTACKER (reveals shared state changes) |

### 4. Progressive Disclosure

Analysts can start with universal (overview) and progressively increase granularity as they narrow their focus. This mirrors the natural investigation workflow: overview → triage → deep dive.

---

## Trade-offs

| Direction | Benefit | Cost |
|-----------|---------|------|
| More universal | Fewer nodes, clearer patterns | Loses per-host specificity |
| More singular | Precise per-instance analysis | More nodes, visual clutter |

The key insight is that there is no single "correct" granularity — it depends on the question being asked. The sliders make this a reversible choice rather than a permanent commitment.

---

## Interaction with Other Readability Mechanisms

- **Visibility toggles**: Work at any granularity level. Hiding CWE/TI is more impactful at high granularity (removes more nodes).
- **CVE merge modes**: Available at all granularity levels, but most useful at high granularity where many duplicate CVEs exist per layer.
- **Environment filtering**: Independent of granularity. Dims CVEs regardless of how they're grouped.

---

## Implementation

Sliders are configured in the Settings modal and require a graph rebuild (`Save & Rebuild`). The backend uses `GraphConfig` to determine node ID construction:

- **Universal**: Node ID is just the concept (e.g., `CVE-2021-44228`)
- **Per-host**: Node ID includes host context (e.g., `CVE-2021-44228@host-001`)
- **Per-CPE**: Node ID includes full ancestor chain (e.g., `CVE-2021-44228@apache:2.4.41@host-001`)

See [GraphNodeConnections.md](GraphNodeConnections.md) for full technical details on slider mechanics and node ID formats.
