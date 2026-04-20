# Readability Mechanism: Visibility Toggles and Filtering

This document describes how PAGDrawer's visibility toggles and environment filters improve attack graph readability by selectively reducing displayed information.

---

## The Readability Problem

A fully expanded attack graph with 6 node types across multiple hosts can easily contain hundreds of nodes and edges. Not every analysis task needs every node type visible. A vulnerability analyst examining CVE-to-impact relationships doesn't need to see every HOST and CPE node. A network architect examining attack surfaces doesn't need CWE weakness categories.

The challenge: **how to reduce information without losing context.**

---

## Mechanism 1: Visibility Toggles (Type Hiding)

### How It Works

Each node type has an eye icon (👁) toggle in the sidebar. Clicking it **hides all nodes of that type** and replaces their connections with **bridge edges** that preserve graph connectivity.

```
Before hiding CVE:    CPE ──HAS_VULN──→ CVE ──IS_INSTANCE_OF──→ CWE
After hiding CVE:     CPE ─────────bridge────────────────────→ CWE
```

### Why Bridge Edges Matter

Naive node hiding (just removing nodes) would disconnect the graph. Bridge edges maintain the "something connects these" relationship while removing the intermediate detail. This is analogous to collapsing a highway map — you lose individual exits but keep the route connections.

### Enabled by Heterogeneity

Visibility toggles are only meaningful in a **heterogeneous** graph. Because each node type occupies a distinct semantic role, hiding "all CWE nodes" removes a coherent conceptual layer rather than random nodes. The graph remains interpretable at a reduced level of detail.

In a homogeneous graph, hiding "all nodes with label starting with CWE-" would remove scattered nodes and break arbitrary paths — a much less useful operation.

### Common Toggle Combinations

| Hidden Types | What Remains | Use Case |
|-------------|-------------|----------|
| None | Full 6-type graph | Complete analysis |
| CWE, TI | HOST → CPE → CVE → VC | "What can be exploited, what does attacker gain?" |
| CWE, TI, VC | HOST → CPE → CVE | Infrastructure vulnerability inventory |
| HOST, CPE | CVE → CWE → TI → VC | Abstract vulnerability impact analysis |
| CWE, TI + merge | HOST → CPE → [CVE groups] → VC | Compact attack path overview |

### Progressive Simplification

Toggles support **progressive simplification** — starting from the full graph and removing layers one at a time to focus attention:

1. **Full graph**: Understand the complete model
2. **Hide CWE**: Remove weakness categorization (often many-to-many and cluttering)
3. **Hide TI**: Remove impact detail, see CVE → VC directly
4. **Enable merge**: Group similar CVEs into compound boxes

Each step reduces visual complexity while maintaining graph connectivity through bridge edges.

---

## Mechanism 2: Environment Filtering (UI/AC)

### How It Works

Two CVSS environmental factors act as **static filters** that dim (but don't remove) CVEs whose requirements aren't met by the environment:

| Factor | Controls | Example |
|--------|----------|---------|
| **User Interaction (UI)** | Are there users who might click things? | Industrial SCADA: UI:N (no users) |
| **Attack Complexity (AC)** | How sophisticated is the attacker? | Script kiddie: AC:L / Nation state: AC:H |

### Visual Encoding

Filtered CVEs receive a **red dashed border** and reduced opacity (`env-filtered` class). This preserves their position in the graph while signaling "this path is blocked in this environment."

### Cascade Propagation

Filtering cascades downstream: if all CVEs feeding a CWE are filtered, the CWE is also dimmed. This cascades through TI → VC, showing which entire attack paths become unavailable.

```
CVE-1 (UI:R) ──→ CWE-79 ──→ TI:XSS ──→ VC:EX:Y
CVE-2 (UI:R) ──→ CWE-79 ┘

Environment: UI:N (no user interaction)
Result: CVE-1, CVE-2, CWE-79, TI:XSS, VC:EX:Y all dimmed
```

### Dim vs. Hide

Environment filtering **dims** rather than **hides** because:
1. The vulnerability still exists — it's just not exploitable in this configuration
2. Analysts should see what they're protected from, not just what threatens them
3. Changing the environment setting instantly reveals/dims paths — no graph rebuild needed

---

## How Filtering Aids Readability

### 1. Attention Guidance

Dimmed nodes recede visually, directing attention to the bright (exploitable) nodes. The analyst's eye naturally focuses on active attack paths without losing awareness of dormant ones.

### 2. Scenario Comparison

Toggling UI from N to R instantly reveals how many additional attack paths open up when users can be tricked. This "what-if" capability turns the graph into an interactive risk model.

### 3. Complexity Budget

On a graph with 200 CVEs, perhaps only 80 are exploitable with UI:N/AC:L. Filtering dims the other 120, giving the analyst a cognitive "complexity budget" of 80 nodes to reason about while keeping the full picture available.

### 4. Layer-Appropriate Simplification

Visibility toggles and environment filters work at different granularities:

| Mechanism | Granularity | Reversibility | Affects Structure |
|-----------|------------|--------------|-------------------|
| Visibility toggles | Entire node type | Instant restore | Yes (bridge edges) |
| Environment filter | Individual CVEs | Instant toggle | No (dims only) |

This lets analysts combine both: hide CWE/TI types for structural simplification, then filter by UI/AC for environmental focus.

---

## Interaction with Other Readability Mechanisms

- **Heterogeneity**: Makes type-based hiding semantically meaningful rather than arbitrary.
- **CVE merge modes**: Visibility toggles enable merge (requires CWE+TI hidden). The two mechanisms compose: first simplify layers, then group nodes.
- **Universality sliders**: Visibility toggles work at any granularity level. Hiding CWE on a per-CVE-granularity graph removes more nodes than on a universal graph.
- **Nominal scales**: Environment filtering uses CVSS UI/AC values — nominal scale data that the graph schema already carries.

---

## Technical Details

For implementation specifics on bridge edges, edge storage, and restoration mechanics, see [GraphNodeConnections.md](GraphNodeConnections.md). For cascade propagation details, see the `applyEnvironmentFilter()` function in `frontend/js/features/environment.ts`.
