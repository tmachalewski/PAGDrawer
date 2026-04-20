# Readability Mechanism: Graph Heterogeneity

This document describes how PAGDrawer's use of **heterogeneous node and edge types** improves attack graph readability compared to homogeneous graph representations.

---

## The Readability Problem

Traditional attack graphs often use **homogeneous** representations — every node is "an attack step" or "a state", and every edge is "leads to". This forces analysts to read labels to understand what each node represents. At scale, this creates a wall of identically-shaped, identically-colored nodes that demands serial label reading.

---

## The Mechanism: Typed Graph Schema

PAGDrawer uses **8 distinct node types** and **9 edge types**, each with unique visual encoding:

### Node Types and Visual Encoding

| Type | Color | Shape Role | Semantic Layer |
|------|-------|-----------|---------------|
| **ATTACKER** | Magenta | Entry point | Who |
| **HOST** | Red | Target asset | Where |
| **CPE** | Orange | Software product | What software |
| **CVE** | Yellow | Vulnerability | What flaw |
| **CWE** | Green | Weakness category | Why it's flawed |
| **TI** | Cyan | Technical Impact | What happens |
| **VC** | Purple | Vector Changer | What changes |
| **BRIDGE** | Teal | Layer transition | Network boundary |

### Edge Types

| Edge | Semantic Meaning | Visual Flow |
|------|-----------------|-------------|
| `ENTERS_NETWORK` | Initial access | Attacker → Host |
| `CAN_REACH` | Network connectivity | VC → Host |
| `RUNS` | Software installation | Host → CPE |
| `HAS_VULN` | Vulnerability presence | CPE → CVE |
| `IS_INSTANCE_OF` | Weakness classification | CVE → CWE |
| `HAS_IMPACT` | Technical consequence | CWE → TI |
| `LEADS_TO` | State change | TI → VC |
| `ENABLES` | Multi-stage prerequisite | VC → CVE |
| `HAS_STATE` | Initial capability | VC → Attacker |

---

## How Heterogeneity Aids Readability

### 1. Pre-Attentive Processing

Color and position allow the human visual system to process node types **before conscious attention**. An analyst can instantly see:
- "There's a cluster of yellow (CVE) nodes connected to one orange (CPE) node" — one software has many vulnerabilities
- "Purple (VC) nodes fan out from cyan (TI)" — this impact produces multiple state changes

This is impossible in a homogeneous graph where all nodes look identical.

### 2. Columnar Layout (Left-to-Right Flow)

The dagre layout positions nodes by type in columns:

```
ATTACKER → HOST → CPE → CVE → CWE → TI → VC
(col 0)   (col 1) (col 2) (col 3) (col 4) (col 5) (col 6)
```

This creates a natural **left-to-right attack narrative**: from attacker through infrastructure, through vulnerabilities, to consequences. An analyst's eye can track an attack path by following edges left to right.

### 3. Semantic Chunking

Each node type represents a different **knowledge domain**:

| Column | Domain | Expert |
|--------|--------|--------|
| HOST, CPE | Infrastructure / asset management | System administrator |
| CVE | Vulnerability management | Security analyst |
| CWE | Software weakness patterns | Developer |
| TI, VC | Attack impact and state | Penetration tester |

This means different stakeholders can focus on "their" column while understanding the overall flow. A developer sees familiar CWE patterns; a sysadmin sees familiar host/software combinations.

### 4. Pattern Recognition

Heterogeneity enables visual patterns that convey meaning without reading labels:

| Visual Pattern | Meaning |
|---------------|---------|
| Many yellow nodes from one orange node | One software has many vulnerabilities |
| One green node feeding many cyan nodes | One weakness type has broad impact |
| Purple node with `ENABLES` edge back to yellow | Multi-stage attack chain |
| Red dashed border on yellow node | Environment-filtered CVE (unreachable) |
| Cluster of yellow nodes in dashed box | Merged CVE group (shared prereqs/outcomes) |

### 5. Filtering Leverage

Because the graph is heterogeneous, **type-based filtering** becomes a powerful readability tool. Hiding all CWE and TI nodes (homogeneous graphs can't do this meaningfully) simplifies CVE → VC relationships while preserving the infrastructure and vulnerability layers.

---

## Comparison with Homogeneous Approaches

### Homogeneous Attack Graph
```
State_1 → State_2 → State_3 → State_4 → State_5
(all same color, shape, and size — must read every label)
```

### PAGDrawer Heterogeneous Graph
```
[Red HOST] → [Orange CPE] → [Yellow CVE] → [Green CWE] → [Cyan TI] → [Purple VC]
(color, position, and shape encode type — labels add detail, not identity)
```

### Practical Impact

| Metric | Homogeneous | Heterogeneous |
|--------|------------|---------------|
| Time to identify node type | Read label (~2s) | Color recognition (~0.2s) |
| Identify attack stage | Read + reason | Column position (instant) |
| Find all vulnerabilities | Scan all labels | Look at yellow column |
| Spot multi-stage chains | Follow edges + read | See purple → yellow `ENABLES` edges |

---

## The 6-Layer Schema

The node types follow a **6-layer semantic model** from Machalewski et al. (2024):

```
Infrastructure Layer:    HOST → CPE          (what exists)
Vulnerability Layer:     CVE                 (what's wrong)
Weakness Layer:          CWE                 (why it's wrong)
Impact Layer:            TI                  (what happens if exploited)
State Layer:             VC                  (what the attacker gains)
```

Each layer answers a different question about the attack surface. The graph's heterogeneity makes these layers visually distinct and independently addressable.

---

## Interaction with Other Readability Mechanisms

- **Visibility toggles**: Heterogeneity is what makes type-based filtering meaningful. In a homogeneous graph, "hide all nodes of type X" removes random-looking nodes. In a heterogeneous graph, it removes a semantic layer.
- **CVE merge modes**: Only possible because CVE is a distinct type with known attributes (prereqs, outcomes). Homogeneous graphs can't selectively merge one category.
- **Universality sliders**: Operate per-type, letting analysts control granularity of infrastructure separately from vulnerability detail.
- **Nominal scale dependencies**: VC nodes encode CVSS dimensions because they are a dedicated type with structured attributes.
