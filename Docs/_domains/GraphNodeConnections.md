# Graph Node Connections and Slider Configurations

This document explains how nodes in the PAGDrawer attack graph are connected, and how the visibility toggles and universality sliders affect the graph structure.

---

## Node Types and Hierarchy

The graph uses a 6-node schema representing an attack progression:

```
ATTACKER → HOST → CPE → CVE → CWE → TI → VC
(entry)   (asset) (sw)  (vuln) (weak) (impact) (state)
```

| Node Type | Description                      | Example                                  |
| --------- | -------------------------------- | ---------------------------------------- |
| **HOST**  | Physical/virtual asset           | `host-001` (a server)                    |
| **CPE**   | Software/OS running on host      | `cpe:2.3:a:apache:http_server:2.4.41`    |
| **CVE**   | Specific vulnerability           | `CVE-2021-44228` (Log4Shell)             |
| **CWE**   | Abstract weakness category       | `CWE-79` (XSS)                           |
| **TI**    | Technical Impact of exploitation | `HIGH_CONFIDENTIALITY`, `HIGH_INTEGRITY` |
| **VC**    | Vector Changer (attacker state)  | `VC:AV:N`, `VC:PR:L`                     |

---

## Edge Types (How Nodes Connect)

### Static Edges (Infrastructure)
| Edge             | Source → Target | Meaning                                  |
| ---------------- | --------------- | ---------------------------------------- |
| `RUNS`           | HOST → CPE      | This host runs this software             |
| `HAS_VULN`       | CPE → CVE       | This software has this vulnerability     |
| `IS_INSTANCE_OF` | CVE → CWE       | This CVE is an instance of this weakness |
| `HAS_IMPACT`     | CWE → TI        | This weakness has this technical impact  |
| `CONNECTED_TO`   | HOST ↔ HOST     | Network reachability                     |

### Dynamic Edges (Attack State Machine)
| Edge             | Source → Target | Meaning                                       |
| ---------------- | --------------- | --------------------------------------------- |
| `LEADS_TO`       | TI → VC         | Technical impact leads to attacker state      |
| `ENABLES`        | VC → CVE        | Having this state enables exploiting this CVE |
| `ENTERS_NETWORK` | ATTACKER → VC   | Initial network entry point                   |
| `CAN_REACH`      | VC → HOST       | Having this access reaches this host          |
| `HAS_STATE`      | HOST → VC       | Host begins with this access state            |

---

## Attack Flow Example

```
ATTACKER
    ↓ (ENTERS_NETWORK via AV:N)
VC:AV:N (Network access)
    ↓ (ENABLES)
HOST:server-01
    ↓ (RUNS)
CPE:apache:http_server:2.4.41
    ↓ (HAS_VULN)
CVE-2021-44228
    ↓ (IS_INSTANCE_OF)
CWE-502 (Deserialization)
    ↓ (HAS_IMPACT)
TI:HIGH_INTEGRITY
    ↓ (LEADS_TO)
VC:PR:H (High privileges gained)
    ↓ (ENABLES next attack...)
```

---

## Vector Changers and Attack Progression

Vector Changers (VCs) are the **core state machine** of the attack graph. They represent what the attacker has **gained** and what they **require** to proceed.

### The Key Insight

> **Gaining a VC unlocks CVEs that require that level OR LESS permissive.**

When you exploit a vulnerability, the technical impact (TI) leads to a new VC state. This new state enables exploitation of CVEs that were previously inaccessible.

### VC Hierarchies

VCs follow hierarchies where gaining a **more restrictive** state implies having **less restrictive** access:

#### Attack Vector (AV) Hierarchy
```
Physical (P) > Local (L) > Adjacent (A) > Network (N)
   most           ←→              →→          least
restrictive                                 restrictive
```

| If you gain...       | You can exploit CVEs requiring... |
| -------------------- | --------------------------------- |
| `VC:AV:N` (Network)  | Only AV:N CVEs                    |
| `VC:AV:A` (Adjacent) | AV:N and AV:A CVEs                |
| `VC:AV:L` (Local)    | AV:N, AV:A, and AV:L CVEs         |
| `VC:AV:P` (Physical) | All attack vectors                |

#### Privileges Required (PR) Hierarchy
```
High (H) > Low (L) > None (N)
 most        →→       least
restrictive         restrictive
```

| If you gain...   | You can exploit CVEs requiring... |
| ---------------- | --------------------------------- |
| `VC:PR:N` (None) | Only PR:N CVEs (no auth needed)   |
| `VC:PR:L` (Low)  | PR:N and PR:L CVEs                |
| `VC:PR:H` (High) | PR:N, PR:L, and PR:H CVEs         |

### Attack Progression Example

```
1. ATTACKER starts with VC:AV:N (network access only)
   └── Can only exploit CVEs with Attack Vector: Network

2. Exploits CVE-2021-44228 (Log4Shell, AV:N, yields local shell)
   └── Gains VC:AV:L (local access)

3. With VC:AV:L, now can exploit CVE-2021-3156 (sudo, AV:L)
   └── This CVE requires local access - was BLOCKED before!
   └── Gains VC:PR:H (root privileges)

4. With VC:PR:H, can exploit CVEs requiring admin rights
   └── Full privilege escalation chain complete
```

### How It's Wired in the Graph

The `ENABLES` edge connects VCs to CVEs based on prerequisites:

```
VC:AV:N ──ENABLES──→ [All CVEs with AV:N]
VC:AV:L ──ENABLES──→ [All CVEs with AV:N, AV:A, or AV:L]
VC:PR:L ──ENABLES──→ [All CVEs with PR:N or PR:L]
```

### Multi-Stage Attack Chains

The graph automatically wires **multi-stage attacks**:

```
CVE-A (requires AV:N, yields AV:L)    CVE-B (requires AV:L, yields PR:H)
        │                                      │
        └──→ VC:AV:L ──ENABLES──→ CVE-B ──→ VC:PR:H
```

This is how the graph represents privilege escalation and lateral movement.

---

## Environmental VCs (Static Filters)

While AV and PR VCs represent **state changes** the attacker gains through exploitation, **UI (User Interaction)** and **AC (Attack Complexity)** are **environmental conditions** set by the defender's environment.

### The Difference

| VC Type                    | Category      | Meaning                                       |
| -------------------------- | ------------- | --------------------------------------------- |
| **AV** (Attack Vector)     | State Mutator | Attacker gains access levels                  |
| **PR** (Privileges Req)    | State Mutator | Attacker gains privilege levels               |
| **UI** (User Interaction)  | Static Filter | Does environment have users who click things? |
| **AC** (Attack Complexity) | Static Filter | Is attacker willing to exploit complex vulns? |

### User Interaction (UI)

Controls whether CVEs requiring user interaction are exploitable:

| UI Setting          | CVEs Exploitable                            |
| ------------------- | ------------------------------------------- |
| **UI:N** (None)     | Only CVEs with UI:N (no user action needed) |
| **UI:R** (Required) | All CVEs (can trick users into clicking)    |

**Use Case**: In an automated industrial environment with no human operators, set UI:N because no one will click phishing links.

### Attack Complexity (AC)

Controls whether complex-to-exploit CVEs are considered:

| AC Setting      | CVEs Exploitable                      |
| --------------- | ------------------------------------- |
| **AC:L** (Low)  | Only CVEs with AC:L (easy to exploit) |
| **AC:H** (High) | All CVEs (attacker is sophisticated)  |

**Use Case**: Against a script kiddie, set AC:L. Against a nation-state actor, set AC:H.

### How It Works in the Graph

Unlike AV/PR which create edges between VCs and CVEs, UI/AC work as **filters**:

1. **CVE Filtering**: CVEs not meeting UI/AC requirements are **dimmed** (`env-filtered` class)
2. **Cascade Propagation**: Dimming propagates to CWE → TI → VC nodes that become unreachable
3. **Visual Feedback**: Filtered nodes appear faded, showing which attack paths are blocked

```
Environment: UI:N, AC:L (no user interaction, simple attacks only)

CVE-2021-44228 (UI:N, AC:L) → ✅ Visible, exploitable
CVE-2022-1234  (UI:R, AC:L) → ⚪ Dimmed (requires user interaction)
CVE-2022-5678  (UI:N, AC:H) → ⚪ Dimmed (too complex for environment)
```

### Setting Environmental VCs

Use the **Environment Settings** panel in the sidebar:

- **User Interaction**: None (UI:N) or Required (UI:R)
- **Attack Complexity**: Low (AC:L) or High (AC:H)

Changes apply immediately without rebuilding the graph.

---

## Universality Sliders (Settings Modal)

The sliders in the Settings modal control **node grouping granularity** - whether nodes are shared globally or duplicated per context.

### Slider Positions

Each slider can be set from **ATTACKER** (leftmost) to **TI** (rightmost):

```
ATTACKER ←──────────────────────────→ Most Granular
(shared)                               (per-instance)
```

| Position     | Meaning                                 |
| ------------ | --------------------------------------- |
| **ATTACKER** | One shared node globally (universal)    |
| **HOST**     | One node per host                       |
| **CPE**      | One node per CPE instance               |
| **CVE**      | One node per CVE instance               |
| **CWE**      | One node per CWE (includes CVE context) |
| **TI**       | Most granular (full context chain)      |

### Valid Grouping Levels Per Node Type

Each node type can only group by its **ancestors** in the hierarchy:

| Node    | Valid Positions                   | Default |
| ------- | --------------------------------- | ------- |
| **CPE** | ATTACKER, HOST                    | HOST    |
| **CVE** | ATTACKER, HOST, CPE               | CPE     |
| **CWE** | ATTACKER, HOST, CPE, CVE          | CVE     |
| **TI**  | ATTACKER, HOST, CPE, CVE, CWE     | CWE     |
| **VC**  | ATTACKER, HOST, CPE, CVE, CWE, TI | TI      |

---

## Slider Effect Examples

### VC Slider at "ATTACKER" (Universal)
- **One `VC:AV:N` node** shared across all hosts
- Gaining network access on Host-A means you have it globally
- Simpler graph, fewer nodes
- Less accurate for multi-host environments

### VC Slider at "HOST" (Per-Host)
- **Separate `VC:AV:N@host-001`** and **`VC:AV:N@host-002`**
- Gaining access on Host-A doesn't imply access on Host-B
- Enables proper multi-stage attack chains

### CVE Slider at "ATTACKER" (Universal)
- **One `CVE-2021-44228` node** regardless of which hosts have it
- All hosts with affected Apache share the same CVE node
- Compact graph, loses host-specific context

### CVE Slider at "CPE" (Per-CPE)
- **`CVE-2021-44228@apache@host-001`** separate from **`CVE-2021-44228@apache@host-002`**
- Each software instance's vulnerability is tracked independently
- Most accurate for exploitation analysis

---

## Node ID Format

Node IDs include context based on slider position:

| Slider Position | Example CVE ID                          |
| --------------- | --------------------------------------- |
| ATTACKER        | `CVE-2021-44228`                        |
| HOST            | `CVE-2021-44228@host-001`               |
| CPE             | `CVE-2021-44228@host-001@apache:2.4.41` |

---

## Visibility Toggles (Eye Buttons)

The 👁 buttons in the sidebar **hide/show entire node types** without affecting the underlying graph structure.

### How Visibility Toggle Works

1. **Hiding a type** (e.g., CVE):
   - Removes all CVE nodes from view
   - Creates **bridge edges** connecting CPE → CWE directly
   - Stores removed nodes/edges for restoration
   - Bridge edges inherit color from hidden edge types

2. **Showing a type**:
   - Removes bridge edges
   - Restores original nodes and their edges

### Bridge Edge Behavior

When hiding intermediate nodes, bridge edges preserve graph connectivity:

```
Before hiding CVE:    CPE → CVE → CWE
After hiding CVE:     CPE ────→ CWE  (bridge edge)
```

Bridge edge color **averages** the colors of hidden edge types for visual indication.

### Multiple Types Hidden

When multiple adjacent types are hidden, global edge storage ensures proper restoration regardless of show/hide order.

---

## Two-Layer Attack Model

The graph uses a **2-layer model** for network intrusion:

### Layer 1: External Attack
- Attacker starts outside network
- Can only use **AV:N** (network) attack vectors
- Initial compromise gives "INSIDE_NETWORK" state

### Layer 2: Internal (Post-Compromise)
- Attacker has network adjacency to all hosts
- Can use **AV:A** (adjacent) attack vectors
- Enables lateral movement between hosts

### Bridge Between Layers
```
Layer 1 EX:Y (exploited) → INSIDE_NETWORK → Layer 2 AV:A access
```

---

## Configuration Interaction Summary

| Feature                         | What It Controls               | Scope                      |
| ------------------------------- | ------------------------------ | -------------------------- |
| **Universality Sliders**        | Node deduplication/granularity | Backend (requires rebuild) |
| **Visibility Toggles**          | Show/hide node types           | Frontend-only (instant)    |
| **Environment Filters (UI/AC)** | Filter exploitable CVEs        | Frontend (dims nodes)      |
| **Node Search**                 | Find nodes by label            | Frontend (highlights)      |

### When to Rebuild vs. Toggle

- **Slider changes** → Require "Save & Rebuild" (changes graph structure)
- **Visibility toggles** → Instant (view modification only)
- **Sliders persist** after page reload
- **Visibility resets** on page reload (stored in memory only)

---

## Default Configuration

```python
{
    "HOST": "ATTACKER",  # Hosts are always anchors
    "CPE": "HOST",       # CPE per host
    "CVE": "CPE",        # CVE per CPE
    "CWE": "CVE",        # CWE per CVE
    "TI": "CWE",         # TI per CWE
    "VC": "TI",          # VC per TI (most granular)
}
```

This provides a **clean linear flow** where each node holds full context from its ancestors.
