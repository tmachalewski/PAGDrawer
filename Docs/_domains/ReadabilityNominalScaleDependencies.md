# Readability Mechanism: Nominal Scale Dependencies (CVSS)

This document describes how PAGDrawer uses **nominal scales from CVSS** to express attack dependencies as structured, interpretable graph edges rather than opaque "leads to" relationships.

---

## The Readability Problem

Traditional attack graphs express dependencies as binary relationships: "exploiting vulnerability A enables exploiting vulnerability B." But they rarely explain **why**. An analyst seeing `CVE-A → CVE-B` must research both CVEs to understand the dependency. At scale, dozens of such edges become an unreadable tangle of unexplained connections.

The challenge: **how to make attack dependencies self-explanatory.**

---

## The Mechanism: CVSS Vector Decomposition

CVSS (Common Vulnerability Scoring System) vectors encode vulnerability characteristics as **nominal scale** values — categorical dimensions with discrete levels:

### CVSS Dimensions Used

| Dimension | Full Name | Values | Scale Type |
|-----------|----------|--------|------------|
| **AV** | Attack Vector | Network (N), Adjacent (A), Local (L), Physical (P) | Ordinal nominal |
| **PR** | Privileges Required | None (N), Low (L), High (H) | Ordinal nominal |
| **UI** | User Interaction | None (N), Required (R) | Binary nominal |
| **AC** | Attack Complexity | Low (L), High (H) | Binary nominal |

These dimensions are **not numeric scores** — they are categorical labels with semantic meaning. PAGDrawer preserves this categorical nature rather than collapsing it into a single CVSS score.

---

## How It Works in the Graph

### Vector Changers (VCs)

Each CVSS dimension becomes a **Vector Changer (VC) node** that represents an attacker's capability state:

```
VC:AV:N  → "Attacker has network access"
VC:AV:L  → "Attacker has local access"
VC:PR:H  → "Attacker has high privileges"
VC:EX:Y  → "Attacker has exploited a vulnerability"
```

### Prerequisites and Outcomes

Every CVE has:
- **Prerequisites**: What CVSS conditions must be met to exploit it (from its CVSS vector)
- **Outcomes**: What new capabilities exploiting it produces (from the CWE → TI → VC chain)

```
CVE-2021-44228 (Log4Shell)
  Prerequisites: AV:N, PR:N       ← needs network access, no auth
  Outcomes:      AV:L, PR:H, EX:Y ← gives local access, high privileges
```

### ENABLES Edges

The `ENABLES` edge connects a VC outcome from one exploit to a CVE that requires it:

```
VC:AV:L:d0  ──ENABLES──→  CVE-2022-2588:d1
```

Reading: "Gaining local access (from a depth-0 exploit) enables exploiting CVE-2022-2588 (at depth 1, because it requires AV:L)."

This edge is self-explanatory — the VC label tells you **what capability** bridges the two exploits.

---

## How Nominal Scales Aid Readability

### 1. Self-Documenting Edges

In a traditional attack graph:
```
CVE-A → CVE-B     (why? must read both CVE descriptions)
```

In PAGDrawer:
```
CVE-A → CWE → TI → VC:AV:L ──ENABLES──→ CVE-B
```

The VC node label (`AV:L`) immediately tells the analyst: "this dependency exists because CVE-A gives local access and CVE-B requires it." No external lookup needed.

### 2. Hierarchical Reasoning

The nominal scales have **ordinal structure** that enables intuitive reasoning:

**Attack Vector hierarchy:**
```
Physical (P) > Local (L) > Adjacent (A) > Network (N)
   most restrictive ←──────────────────→ least restrictive
```

**Privileges Required hierarchy:**
```
High (H) > Low (L) > None (N)
```

Gaining a higher level **subsumes** lower levels. If an attacker gains `AV:L` (local), they can exploit CVEs requiring `AV:L`, `AV:A`, or `AV:N`. This hierarchy is visually represented — a single `VC:AV:L` node can have `ENABLES` edges to multiple CVEs at different AV levels.

### 3. Pattern Recognition Across CVEs

Because prerequisites are expressed in the same nominal scale vocabulary, analysts can instantly spot patterns:

- "All depth-0 CVEs require `AV:N, PR:N`" → all initial exploits are unauthenticated remote
- "The depth-1 CVE requires `AV:L, PR:L`" → privilege escalation requires local access
- "Five CVEs share prereqs `AV:N/AC:L/PR:N/UI:N`" → five interchangeable entry points

This is what enables the **CVE merge by prerequisites** mode — CVEs can be grouped by their nominal-scale requirement signature.

### 4. Environmental Reasoning

The UI and AC dimensions serve as **environment switches** rather than attack progression states:

| Dimension | Question | Effect |
|-----------|----------|--------|
| UI:N vs UI:R | "Are there users who click things?" | Filters CVEs requiring user interaction |
| AC:L vs AC:H | "Is the attacker sophisticated?" | Filters high-complexity CVEs |

These are binary nominal values that an analyst can set based on **environmental knowledge** (not vulnerability knowledge). The graph instantly reflects which paths are viable in that environment.

### 5. Outcome-Based Grouping

Because outcomes are expressed in the same nominal vocabulary as prerequisites, the **CVE merge by outcomes** mode can identify functionally equivalent CVEs:

```
CVE-A outcomes: [AV:L, PR:H, EX:Y]
CVE-B outcomes: [AV:L, PR:H, EX:Y]
CVE-C outcomes: [EX:Y]             ← different outcomes, separate group
```

CVE-A and CVE-B are interchangeable from the attacker's perspective — they produce the same state change. This insight is only possible because outcomes are structured nominal-scale data rather than free-text descriptions.

---

## The Consensual Transformation Matrix

The mapping from Technical Impacts (TI) to Vector Changers (VC) is defined by the **Consensual Transformation Matrix** from Machalewski et al. (2024). This matrix was derived from expert consensus on 22 CVEs, mapping 24 Technical Impact categories to VC state changes.

The matrix ensures that the nominal-scale dependency representation is grounded in **domain expertise**, not arbitrary assignment. For example:

| Technical Impact | VC Produced | Rationale |
|-----------------|-------------|-----------|
| Execute Unauthorized Code | AV:L, PR:H, EX:Y | Code execution gives local access and high privileges |
| Bypass Protection Mechanism | PR:L | Bypassing auth grants low-level access |
| Read Data | (no state change) | Reading data doesn't change attacker capabilities |

---

## Comparison with Score-Based Approaches

### CVSS Score (Numeric)
```
CVE-2021-44228: CVSS 10.0
CVE-2022-2588:  CVSS 7.8
```
A single number — high score means "bad" but tells nothing about dependencies between vulnerabilities or why one enables another.

### PAGDrawer (Nominal Scales)
```
CVE-2021-44228: requires AV:N/PR:N, produces AV:L/PR:H/EX:Y
CVE-2022-2588:  requires AV:L/PR:L, produces PR:H/EX:Y
                         ↑ satisfied by ↑
```
The nominal dimensions make the dependency chain **visible and self-explanatory**.

---

## Interaction with Other Readability Mechanisms

- **Heterogeneity**: VC nodes are a dedicated type with structured attributes. Without heterogeneity, prerequisite/outcome data would be embedded in generic nodes.
- **CVE merge modes**: Both merge strategies use nominal-scale data — prereqs groups by CVSS dimensions, outcomes groups by VC state vectors.
- **Visibility toggles**: When CWE/TI are hidden, the nominal-scale information is preserved in bridge edges (CVE → VC) and in CVE node attributes.
- **Universality sliders**: VC node granularity controls whether `VC:AV:L` is shared globally or per-host. Both granularities preserve the nominal-scale semantics.

---

## References

- **CVSS v3.1 Specification**: Defines the nominal scale dimensions (AV, AC, PR, UI, S, C, I, A)
- **Machalewski et al. (2024)**: "Expressing Impact of Vulnerabilities" — defines the Consensual Transformation Matrix mapping TI to VC
- **NIST NVD**: Source of per-CVE CVSS vectors used to populate prerequisite data
