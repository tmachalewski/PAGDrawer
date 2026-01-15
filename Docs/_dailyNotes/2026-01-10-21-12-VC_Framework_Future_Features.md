# PAGDrawer Future Features from VC Framework Paper

> Created: 2026-01-10T21:12
> Based on: Machalewski et al. (2024) - "Expressing Impact of Vulnerabilities"

This document outlines additional features from the VC Framework paper that could be implemented in PAGDrawer.

---

## ✅ Already Implemented (This Session)

### 1. VC Prerequisite Hierarchy
**Status**: ✅ Implemented

Higher privilege levels satisfy lower privilege requirements:
- `AV: N < A < L < P` - Local (L) satisfies Network (N), Adjacent (A), Local (L)
- `PR: N < L < H` - High (H) satisfies None (N), Low (L), High (H)

**File**: `src/graph/builder.py` - `_wire_multistage_attacks()`

### 2. EX:Y as Terminal Goal Node
**Status**: ✅ Implemented

`EX:Y` (Exploited: Yes) nodes are marked as terminal with:
- `is_terminal: true` attribute
- Special visual styling (red star with gold border)
- Label "EXPLOITED"

**Files**: 
- `src/graph/builder.py` - `_wire_cwe_to_vcs()`
- `frontend/index.html` - Cytoscape styling

---

## 🔮 Planned Features

### 3. AC/UI Environmental VCs as Probability Modifiers

**Concept**: Attack Complexity (AC) and User Interaction (UI) are "environmental VCs" that don't change during attack progression but affect success probability.

**Paper Reference**: 
> "Attack Complexity (AC) and User Interaction (UI) were used as indicators of environmental factors describing attacker and host user. AC and UI VCs were grouped into environmental VCs."

**Implementation**:
```python
# In consensual_matrix.py (already exists partially)
def extract_environmental_filters(cvss_vector: str) -> Dict[str, float]:
    """
    AC:H (high complexity) -> 0.5 probability
    AC:L (low complexity) -> 1.0 probability
    UI:R (user required) -> 0.4 probability  
    UI:N (none required) -> 1.0 probability
    """
```

**UI Changes**:
- Show path probability = EPSS × AC_factor × UI_factor
- Color edges by probability (green=high, red=low)
- Filter paths below threshold

**Effort**: Medium (~2-3 hours)

---

### 4. Cross-Host Attack Pivoting

**Concept**: VCs gained on one host can enable attacks on connected hosts through network edges.

**Paper Reference**:
> "For attack graphs construction, representing consequences of vulnerability is needed... consequences of downstream vulnerability could be used as a prerequisite for possibility of exploiting another vulnerability."

**Current State**: ENABLES edges only connect VCs to CVEs on the **same host**

**Implementation**:
```python
def _wire_cross_host_pivoting(self):
    """
    When host-A gains AV:L, and host-A CAN_REACH host-B,
    create edge: VC:AV:L@host-A -> PIVOT -> host-B
    This enables attacking host-B as if attacker is "adjacent"
    """
```

**Example**:
1. Attacker → DMZ-server (via Log4j RCE) → gains AV:L on DMZ
2. DMZ CAN_REACH internal-db
3. Attacker pivots → internal-db (now adjacent to internal network)
4. Attacker exploits internal CVE requiring AV:A

**Effort**: Medium-High (~3-4 hours)

---

### 5. Real CVE Data Integration

**Concept**: Load CVEs with expert-assigned Technical Impacts from the paper's dataset.

**Paper Reference**:
> "We made the dataset available at https://github.com/tmachalewski/CVEsImpactDataset"
> "Dataset described below is available at https://github.com/tmachalewski/CVEsImpactDataset"

**Dataset Contains** (for 22 CVEs):
- Official NVD descriptions
- Expert CVSS scores (3 experts independently)
- Technical Impact binary indicators
- Vector Changer assignments
- CWE mappings

**Implementation**:
1. Add data loader for CSV/JSON from dataset repo
2. Create API endpoint `/api/load-cves` 
3. Map dataset format to PAGDrawer's mock_data structure
4. Add UI to select dataset source (mock vs real)

**Effort**: Medium (~2-3 hours)

---

### 6. Attack Path Probability Calculation

**Concept**: Calculate overall probability of an attack path succeeding.

**Paper Reference**:
> "Attack graphs have also been extended with probabilistic component, describing likelihood of adversary's actions"

**Formula**:
```
P(attack_path) = ∏ P(CVE_i exploited)
               = ∏ (EPSS_i × AC_factor_i × UI_factor_i)
```

**Implementation**:
```python
def calculate_path_probability(path: List[str]) -> float:
    """
    Calculate success probability for an attack path.
    
    Args:
        path: List of node IDs [Attacker, Host, CVE1, CWE1, VC1, CVE2, ...]
    
    Returns:
        Cumulative probability (0.0 to 1.0)
    """
    prob = 1.0
    for node_id in path:
        node = graph.nodes[node_id]
        if node['node_type'] == 'CVE':
            epss = node.get('epss_score', 0.5)
            ac_factor = 0.5 if 'AC:H' in node.get('cvss_vector', '') else 1.0
            ui_factor = 0.4 if 'UI:R' in node.get('cvss_vector', '') else 1.0
            prob *= epss * ac_factor * ui_factor
    return prob
```

**UI Changes**:
- Show probability on each exploit path
- Rank paths by probability
- Heat map coloring on paths

**Effort**: Low-Medium (~1-2 hours)

---

### 7. Transformation Matrix Visualization

**Concept**: Display the Consensual Matrix (Table 1) as an interactive reference.

**Paper Reference**: Table 1 - "The Consensually Agreed Transformation Matrix"

**Implementation**:
- Add modal or sidebar showing matrix
- Click Technical Impact → highlights related CVEs
- Click VC outcome → highlights related CWEs

**Effort**: Low (~1 hour)

---

## Priority Recommendations

| #   | Feature              | Impact    | Effort | Priority |
| --- | -------------------- | --------- | ------ | -------- |
| 3   | AC/UI Probabilities  | High      | Medium | ⭐⭐⭐      |
| 6   | Path Probability     | High      | Low    | ⭐⭐⭐      |
| 4   | Cross-Host Pivoting  | Very High | High   | ⭐⭐       |
| 5   | Real CVE Data        | Medium    | Medium | ⭐⭐       |
| 7   | Matrix Visualization | Low       | Low    | ⭐        |

---

## References

- Machalewski, T., Szymanek, M., Czubak, A., & Turba, T. (2024). "Expressing Impact of Vulnerabilities: An Expert-Filled Dataset and Vector Changer Framework for Modelling Multistage Attacks, Based on CVE, CVSS and CWE." Communications of the ECMS, Volume 38, Issue 1.
- Dataset: https://github.com/tmachalewski/CVEsImpactDataset
