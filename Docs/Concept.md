# Thesis Methodology: Detailed Solutions & Architectural Definitions :contentReference[oaicite:0]{index=0}

**Title:** Modelling Multistage Cyberattacks with NLP and Graph Machine Learning Methods  
**Date:** January 2026  
**Document Type:** Methodology Chapter Summary  

---

## 1. Introduction & Architectural Philosophy

This thesis proposes a novel framework for predicting cyber risk by shifting the modeling paradigm from **reactive Event-Based Logging** to **predictive Knowledge-Driven Graphing**. Traditional approaches in cybersecurity risk management often rely on analyzing historical logs (e.g., SIEM data, Sysmon traces), which suffer from significant limitations: they are noisy, sparse, reactive, and often fail to capture the "unknown unknowns" of potential attack paths that have not yet been traversed.

### \[SELECTED STRATEGY\] Knowledge-Driven Digital Twin

Our approach constructs a **Heterogeneous Knowledge Graph** that acts as a "Digital Twin" of the attack surface. By overlaying a synthetic physical infrastructure (Hosts and Software) with a semantic knowledge base of vulnerabilities (CVEs and CWEs), we create a rich environment for simulating hypothetical attack paths. This structure allows us to train **Graph Neural Networks (GNNs)** to predict the likelihood of compromise based on the structural and semantic properties of the network, rather than just historical precedence. This moves the field from "Anomaly Detection" (what is weird?) to "Risk Forecasting" (what is dangerous?).

---

## 2. Graph Architecture: The Heterogeneous Knowledge Graph

To maintain computational efficiency for GNN training while capturing the necessary semantic depth for multistage analysis, the graph schema is strictly defined. We reject the use of "Log Nodes" (like Process IDs or File Handles) in favor of "Concept Nodes" that represent the capability landscape.

### 2.1 Node Schema Definitions

#### \[SELECTED\] The 5-Node Schema

We limit the graph to five distinct node types. This schema explicitly separates physical assets from abstract vulnerability concepts and sets the stage for our "Vector Changer" state machine logic.

| Node Type | Role in Graph | Data Source | Features (Attributes) |
|---|---|---|---|
| **Host** | Infrastructure Root. Represents the physical or virtual asset acting as the "Battlefield." | Synthetic Topology Generation | OS_Family (e.g., Linux, Windows)<br>Criticality_Score (0.0 - 1.0)<br>Subnet_ID (Defines network reachability) |
| **CPE** | Attack Surface. Represents the specific software instance installed on a host. | Generated via Zipf's Law | Vendor (e.g., Apache)<br>Product (e.g., HTTP Server)<br>Version (e.g., 2.4.41)<br>Edition (e.g., Enterprise) |
| **CVE** | The Exploit. Represents the specific flaw that can be triggered. | NVD (National Vulnerability Database) | NLP: S-BERT Embedding of the description (768-dim vector).<br>Threat: EPSS Score (Time Series of last 30 days).<br>Tech: Parsed CVSS Vector String components. |
| **CWE** | Semantic Anchor. Represents the abstract weakness or root cause. | MITRE CWE List | NLP: S-BERT Embedding of the generalized weakness description.<br>Utility: Clusters semantically similar CVEs (e.g., all Buffer Overflows). |
| **VC** | The Vector Changer. Represents the state required or gained by an attacker. | Derived from Machalewski et al. (2024) | Type: AV, PR, AC, UI, EX.<br>Value: e.g., AV:Network, PR:High, UI:Required. |

### 2.2 Edge Schema (Static & Dynamic)

The edges in the graph define relationships of logical implication and physical connection. Crucially, we utilize the "Vector Changer" nodes to mediate connections between vulnerabilities, avoiding the \(O(N^2)\) complexity of fully connecting CVEs.

**Static edges:**
- **Structural:** Host \(\xrightarrow{\text{RUNS}}\) CPE (Defines the software stack).
- **Knowledge:** CPE \(\xrightarrow{\text{HAS_VULN}}\) CVE (Links software to defects).
- **Semantic:** CVE \(\xrightarrow{\text{IS_INSTANCE_OF}}\) CWE (Hierarchical clustering).
- **Topological:** Host \(\xrightarrow{\text{CONNECTED_TO}}\) Host (Network reachability).

#### \[SELECTED\] Dynamic State Machine Edges
- VC \(\xrightarrow{\text{ALLOWS_EXPLOIT}}\) CVE: (Pre-condition) The VC state required to attempt the exploit.
- CVE \(\xrightarrow{\text{YIELDS_STATE}}\) VC: (Post-condition) The VC state gained upon successful exploitation.

---

## 3. Data Population Strategy: Zipfian Distribution

A major challenge in cyber-simulation is assigning software versions to simulated hosts. Real-world scan data is often biased by firewalls (hiding internal versions) or incomplete. To ensure our synthetic graph remains scientifically rigorous and reproducible, we reject ad-hoc sampling in favor of a theoretical distribution model.

### \[SELECTED\] The Zipf's Law (Power Law) Strategy

We model the distribution of software versions using Zipf's Law, a specific instance of the Power Law distribution. This decision is grounded in the "Rich Get Richer" dynamic of software adoption: the most recent stable versions are exponentially more common than older ones, yet a persistent "Long Tail" of legacy versions exists, providing the necessary vulnerability landscape for multistage attacks.

### 3.1 Mathematical Definition

For any given software product (e.g., Nginx, OpenSSL, Java), we define the probability \(P(k)\) of a host running the \(k\)-th most recent version as:

\[
P(k) = \frac{1/k^s}{\sum_{n=1}^{N} (1/n^s)}
\]

Where:
- \(k\): The rank of the version (Rank 1 = Newest release, Rank N = Oldest supported release).
- \(s\): The decay parameter (typically \(s \approx 1.0\) for software ecosystem adoption).
- \(N\): The total number of historical versions considered.

### 3.2 Implementation Workflow

1. **Cataloging:** For a target CPE (e.g., `cpe:2.3:a:apache:http_server`), we fetch the complete list of version strings from the NVD or vendor changelogs.
2. **Ranking:** We sort these versions by Release Date (Newest to Oldest).
3. **Probability Assignment:** We calculate the Zipfian probability for each version.  
   - Example: If we consider 50 versions of Apache, the newest version might have \(P \approx 15\%\), the second newest \(P \approx 7\%\), while the 50th newest version has \(P < 0.1\%\).
4. **Assignment:** When generating a synthetic Host node, we sample its CPE version using these weighted probabilities.

**Justification:** This strategy guarantees that our graph contains a realistic mix of "Secure/Patched" nodes (the head of the distribution) and "Vulnerable/Legacy" nodes (the tail), without relying on potentially biased external datasets.

---

## 4. Edge Logic: The "Vector Changer" Framework

We reject the naive approach of connecting vulnerabilities based solely on shared keywords. Instead, we adopt the Vector Changer (VC) framework (Machalewski et al., 2024), treating vulnerabilities as State-Transition Functions.

### \[SELECTED\] The Petri Net-like State Machine

The CVSS vector is deconstructed into explicit VC Nodes. We categorize these VCs into two functional groups: **State Mutators** (which change the topology) and **Static Filters** (which change the probability).

### 4.1 Group A: Exploitation VCs (State Mutators)

These nodes represent the "Vector Changer" concept physically in the graph. They decouple the Vulnerability from the Access Level.

**Node Types:**
1. **Attack Vector (AV):** Represents location (Network, Adjacent, Local, Physical).
2. **Privileges Required (PR):** Represents permission level (None, Low, High).
3. **Exploited (EX):** Represents the final compromise state.

#### Transformation Logic (The Matrix)

Unlike Prerequisites (which are read directly from CVSS), the Consequences of a CVE are derived using the Technical Impact (TI) Transformation Matrix defined in the reference paper.

1. **NLP Analysis:** We process the CVE description using S-BERT to identify the Technical Impact (e.g., "Execute Unauthorized Code").
2. **Matrix Lookup:** We map the TI to the resulting VC via the expert-defined matrix (e.g., Execute Code \(\to\) AV:Local + PR:Low).
3. **Edge Creation:** We draw a **YIELDS_STATE** edge from the CVE to the resulting VC nodes.

### 4.2 Group B: Environmental VCs (Static Filters)

These VCs represent the environmental conditions required for the exploit. They act as Probabilistic Gates.

**Node Types:**
1. **Attack Complexity (AC):** Low vs High.
2. **User Interaction (UI):** None vs Required.

**Role:** These nodes do not generate new capabilities. Instead, they act as weights. If a CVE requires UI:Required, the edge connecting VC(UI:Required) to CVE carries a probability penalty (e.g., 0.4), reflecting the chance that the user does not interact.

---

## 5. Probability Attribution: Semantic Axis Projection

Assigning numerical probabilities to ordinal rankings (like "High", "Medium", "Low") is often done via arbitrary heuristics. We replace this with a mathematically rigorous method to determine \(P_{success}\) (Probability of Technical Success).

### \[SELECTED\] Semantic Axis Projection

We utilize NLP to derive probabilities from the definitions of reliability found in exploit frameworks (Metasploit).

### 5.1 The Algorithm

1. **Define the Semantic Axis:** We construct a geometric axis in the high-dimensional S-BERT embedding space that represents the concept of "Exploit Reliability."
   - Positive Pole (\(V_{pos}\)): Calculated as the average embedding of positive keywords: \["Stable", "Reliable", "Guaranteed", "Consistent", "Automatic"\].
   - Negative Pole (\(V_{neg}\)): Calculated as the average embedding of failure keywords: \["Crash", "Unreliable", "Unstable", "Impossible", "Manual"\].
   - Axis Vector (\(V_{axis}\)): The vector difference \(V_{pos} - V_{neg}\), creating a direction from "Failure" to "Success."
2. **Project:** For each discrete Metasploit Rank (\(R\)), we compute its scalar projection onto this derived axis.
   - Formula:  
     \[
     Score_{raw} = \frac{V_{R} \cdot V_{axis}}{||V_{axis}||}
     \]
   - Intuition: This measures how "aligned" the word "Excellent" is with the concept of "Guaranteed Success" versus "System Crash."
3. **Normalize:** We apply Min-Max scaling to transform the raw projection scores into a usable probability range \([0, 1]\), yielding our final \(P_{success}\). This value is used to weight the transitions through Environmental VC nodes (AC/UI).

---

## 6. Ground Truth: The Monte Carlo "VC-Walker"

To train the GNN, we need labeled data on which attack paths are actually viable. Since real-world logs of successful multistage attacks are scarce, we generate synthetic ground truth using a Monte Carlo simulation.

### \[SELECTED\] The Two-Step Simulation Strategy

This simulation explicitly distinguishes between Threat (Intent) and Vulnerability (Capability), modeling the attacker as a probabilistic agent traversing the VC-Graph.

### 6.1 Simulation Step Logic

The Walker stands at a set of active VC Nodes (e.g., AV:Network, PR:None).

#### Step 1: Selection (The Intent Check)
- The walker identifies all CVEs connected to the current active VCs via **ALLOWS_EXPLOIT** edges.
- Metric: **EPSS** (Exploit Prediction Scoring System).
- Logic: Weighted Random Choice based on EPSS.
- Interpretation: The attacker chooses which "door" to try based on global popularity and threat intelligence trends. They are more likely to attempt a high-EPSS vulnerability.

#### Step 2: Transition (The Capability Check)
- The walker checks the Environmental VCs required by the chosen CVE (e.g., AC:High).
- Metric: \(P_{success}\) (derived from Semantic Axis Projection).
- Logic: The walker rolls a "Technical Die" (\(r \sim U[0,1]\)).
- Condition:
  - If \(r < P_{success}\): The exploit works. The walker follows the **YIELDS_STATE** edge to activate the new Exploitation VCs (e.g., PR:High).
  - If \(r \ge P_{success}\): The exploit fails (e.g., system crash, detection). The walker remains at the current state.

---

## 7. The Learning Goal: Heterogeneous Graph Transformer (HGT)

The ultimate goal of this thesis is not just to run simulations, but to train a model that can predict the outcome of these simulations instantaneously.

### \[SELECTED\] Model Architecture

We utilize the **Heterogeneous Graph Transformer (HGT)** architecture.

- Why HGT? Unlike standard GCNs, HGT is designed to handle graphs with multiple node types (Host vs CVE vs VC) and multiple edge types (ALLOWS vs YIELDS). It learns specific attention weights for each meta-path.
- Input: The Explicit VC-Graph (Topology + VC Nodes + CVE Semantics).
- Target: Predict the likelihood of activating the VC(EX:Compromised) node from a given entry point.
- Thesis Contribution:  
  "By automating the 'Vector Changer' framework using NLP-driven Technical Impact mapping, we can construct high-fidelity attack graphs that explicitly model the state transitions of multistage attacks. This enables the HGT to learn latent representations of 'Privilege States,' allowing it to generalize attack paths across different vulnerabilities that share the same structural impact."
