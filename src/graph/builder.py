"""
Graph Builder - Assembles the Heterogeneous Knowledge Graph.

Constructs the full graph with:
- Host, CPE, CVE, CWE, VC nodes
- Static edges (RUNS, HAS_VULN, IS_INSTANCE_OF, CONNECTED_TO)
- Dynamic VC edges (ALLOWS_EXPLOIT, YIELDS_STATE)
"""

from typing import Dict, List, Optional, Any, TYPE_CHECKING
import networkx as nx

if TYPE_CHECKING:
    from src.data.loaders import LoadedData

from src.core.schema import (
    NodeType, EdgeType, VCType,
    HostNode, CPENode, CVENode, CWENode, VCNode, Edge,
    create_vc_id, parse_cvss_vector
)
from src.core.consensual_matrix import transform_cve_to_vc_edges
from src.core.config import GraphConfig, DEFAULT_CONFIG


class KnowledgeGraphBuilder:
    """
    Builds and manages the Heterogeneous Knowledge Graph.
    
    The graph uses NetworkX for flexibility, with node/edge attributes
    storing type information for later conversion to PyG format.
    """
    
    def __init__(self, config: GraphConfig = None):
        self.graph = nx.DiGraph()
        self._node_registry: Dict[str, Any] = {}
        self._vc_nodes: Dict[str, VCNode] = {}
        self.config = config or DEFAULT_CONFIG
        self._loaded_data: Optional["LoadedData"] = None
    
    # =========================================================================
    # NODE ADDITION METHODS
    # =========================================================================
    
    def add_host(self, host_data: Dict) -> str:
        """Add a Host node to the graph."""
        host = HostNode(
            id=host_data["id"],
            os_family=host_data["os_family"],
            criticality_score=host_data["criticality_score"],
            subnet_id=host_data["subnet_id"]
        )
        
        self.graph.add_node(
            host.id,
            node_type=NodeType.HOST.name,
            os_family=host.os_family,
            criticality_score=host.criticality_score,
            subnet_id=host.subnet_id
        )
        self._node_registry[host.id] = host
        return host.id
    
    def add_cpe(self, cpe_data: Dict) -> str:
        """Add a CPE node to the graph."""
        cpe = CPENode(
            id=cpe_data["id"],
            vendor=cpe_data["vendor"],
            product=cpe_data["product"],
            version=cpe_data["version"],
            edition=cpe_data.get("edition")
        )
        
        self.graph.add_node(
            cpe.id,
            node_type=NodeType.CPE.name,
            vendor=cpe.vendor,
            product=cpe.product,
            version=cpe.version
        )
        self._node_registry[cpe.id] = cpe
        return cpe.id
    
    def add_cve(self, cve_data: Dict) -> str:
        """Add a CVE node to the graph."""
        cve = CVENode(
            id=cve_data["id"],
            description=cve_data["description"],
            epss_score=cve_data["epss_score"],
            cvss_vector=cve_data["cvss_vector"]
        )
        
        self.graph.add_node(
            cve.id,
            node_type=NodeType.CVE.name,
            description=cve.description,
            epss_score=cve.epss_score,
            cvss_vector=cve.cvss_vector
        )
        self._node_registry[cve.id] = cve
        return cve.id
    
    def add_cwe(self, cwe_data: Dict) -> str:
        """Add a CWE node to the graph."""
        cwe = CWENode(
            id=cwe_data["id"],
            name=cwe_data["name"],
            description=cwe_data["description"]
        )
        
        self.graph.add_node(
            cwe.id,
            node_type=NodeType.CWE.name,
            name=cwe.name,
            description=cwe.description
        )
        self._node_registry[cwe.id] = cwe
        return cwe.id
    
    # =========================================================================
    # EDGE ADDITION METHODS
    # =========================================================================
    
    def add_edge(self, source: str, target: str, edge_type: EdgeType, weight: float = 1.0):
        """Add an edge to the graph."""
        self.graph.add_edge(
            source,
            target,
            edge_type=edge_type.name,
            weight=weight
        )
    
    def connect_host_to_cpe(self, host_id: str, cpe_id: str):
        """Create RUNS edge: Host -> CPE."""
        self.add_edge(host_id, cpe_id, EdgeType.RUNS)
    
    def connect_cpe_to_cve(self, cpe_id: str, cve_id: str):
        """Create HAS_VULN edge: CPE -> CVE."""
        self.add_edge(cpe_id, cve_id, EdgeType.HAS_VULN)
    
    def connect_cve_to_cwe(self, cve_id: str, cwe_id: str):
        """Create IS_INSTANCE_OF edge: CVE -> CWE."""
        self.add_edge(cve_id, cwe_id, EdgeType.IS_INSTANCE_OF)
    
    def connect_hosts(self, host1_id: str, host2_id: str):
        """Create bidirectional CONNECTED_TO edges between hosts."""
        self.add_edge(host1_id, host2_id, EdgeType.CONNECTED_TO)
        self.add_edge(host2_id, host1_id, EdgeType.CONNECTED_TO)
    
    def wire_cve_to_vcs(self, cve_id: str, cvss_vector: str, technical_impact: str):
        """
        Create the VC state machine edges for a CVE.
        
        This is the core Vector Changer wiring:
        - VC -> CVE (ALLOWS_EXPLOIT): Prerequisites to attempt exploit
        - CVE -> VC (YIELDS_STATE): Gains after successful exploitation
        
        NOTE: Only creates YIELDS_STATE edges for escalations (higher privilege/access)
        """
        from src.core.consensual_matrix import AV_HIERARCHY, PR_HIERARCHY
        
        transformation = transform_cve_to_vc_edges(cve_id, cvss_vector, technical_impact)
        
        # Build prereq lookup for escalation checking
        prereq_levels = {}
        for vc_type, vc_value in transformation["prerequisites"]:
            if vc_type == "AV":
                prereq_levels["AV"] = AV_HIERARCHY.get(vc_value, 0)
            elif vc_type == "PR":
                prereq_levels["PR"] = PR_HIERARCHY.get(vc_value, 0)
        
        # Create ALLOWS_EXPLOIT edges (VC -> CVE)
        for vc_type, vc_value in transformation["prerequisites"]:
            vc_id = create_vc_id(VCType[vc_type], vc_value)
            if vc_id in self._vc_nodes:
                self.add_edge(vc_id, cve_id, EdgeType.ALLOWS_EXPLOIT)
        
        # Create YIELDS_STATE edges (CVE -> VC) - only for escalations
        for vc_type, vc_value in transformation["outcomes"]:
            # Check if this is an escalation
            is_escalation = True
            
            if vc_type == "AV":
                outcome_level = AV_HIERARCHY.get(vc_value, 0)
                prereq_level = prereq_levels.get("AV", 0)
                # AV escalation means moving "inward" (higher number)
                is_escalation = outcome_level > prereq_level
            elif vc_type == "PR":
                outcome_level = PR_HIERARCHY.get(vc_value, 0)
                prereq_level = prereq_levels.get("PR", 0)
                # PR escalation means gaining more privileges (higher number)
                is_escalation = outcome_level > prereq_level
            elif vc_type == "EX":
                # Exploited state is always valid
                is_escalation = True
            
            if is_escalation:
                vc_id = create_vc_id(VCType[vc_type], vc_value)
                if vc_id in self._vc_nodes:
                    self.add_edge(cve_id, vc_id, EdgeType.YIELDS_STATE)
    
    def _wire_cwe_to_vcs(
        self,
        cwe_id: str,
        host_id: Optional[str],
        cpe_id: Optional[str],
        cve_id: Optional[str],
        cvss_vector: str,
        technical_impacts: List[str],
        layer_suffix: str = ""
    ):
        """
        Create TI and VC nodes connected from CWE.

        Flow: CWE → TI → VC (for each technical impact)

        Args:
            cwe_id: The CWE node to connect from
            host_id: Host context (if config includes HOST)
            cpe_id: CPE context (if config includes CPE)
            cve_id: CVE context (if config includes CVE)
            cvss_vector: CVSS string for extracting outcomes
            technical_impacts: List of technical impacts for consensual matrix
            layer_suffix: Suffix for layer identification (empty for L1, ":INSIDE_NETWORK" for L2)
        """
        from src.core.consensual_matrix import (
            AV_HIERARCHY, PR_HIERARCHY, transform_cve_to_vc_edges
        )

        # Skip if no technical impacts
        if not technical_impacts:
            return

        is_layer_2 = layer_suffix != ""

        # Process each technical impact
        for technical_impact in technical_impacts:
            transformation = transform_cve_to_vc_edges(cwe_id, cvss_vector, technical_impact)

            # Build prereq lookup for escalation checking
            prereq_levels = {}
            for vc_type, vc_value in transformation["prerequisites"]:
                if vc_type == "AV":
                    prereq_levels["AV"] = AV_HIERARCHY.get(vc_value, 0)
                elif vc_type == "PR":
                    prereq_levels["PR"] = PR_HIERARCHY.get(vc_value, 0)

            # Create TI node (Technical Impact)
            # TI can be grouped by ATTACKER (universal), HOST, CPE, CVE, or CWE
            ti_label = technical_impact

            if self.config.is_universal("TI"):
                ti_id = f"TI:{technical_impact}{layer_suffix}"  # universal within layer
            elif self.config.should_include_context("TI", "CWE"):
                ti_id = f"TI:{technical_impact}@{cwe_id}"  # per-CWE (most granular)
            else:
                ti_id = f"TI:{technical_impact}@{host_id}"  # per-HOST

            if not self.graph.has_node(ti_id):
                self.graph.add_node(
                    ti_id,
                    node_type="TI",
                    impact=technical_impact,
                    label=ti_label,
                    description=f"Technical Impact: {technical_impact}",
                    layer="L2" if is_layer_2 else "L1",
                    host_id=host_id if self.config.should_include_context("TI", "HOST") else None,
                    cwe_id=cwe_id if self.config.should_include_context("TI", "CWE") else None
                )

            # CWE → TI (HAS_IMPACT edge)
            if cwe_id and self.graph.has_node(cwe_id):
                if not self.graph.has_edge(cwe_id, ti_id):
                    self.graph.add_edge(
                        cwe_id,
                        ti_id,
                        edge_type="HAS_IMPACT"
                    )

            # Create outcome VCs connected FROM TI (only for escalations)
            for vc_type, vc_value in transformation["outcomes"]:
                is_escalation = True

                if vc_type == "AV":
                    outcome_level = AV_HIERARCHY.get(vc_value, 0)
                    prereq_level = prereq_levels.get("AV", 0)
                    is_escalation = outcome_level > prereq_level
                elif vc_type == "PR":
                    outcome_level = PR_HIERARCHY.get(vc_value, 0)
                    prereq_level = prereq_levels.get("PR", 0)
                    is_escalation = outcome_level > prereq_level
                elif vc_type == "EX":
                    is_escalation = True

                if is_escalation:
                    # Determine VC ID based on config - check from most specific to least
                    if self.config.should_include_context("VC", "TI"):
                        # Most granular: per-TI (VC inherits TI's full context)
                        vc_id = f"VC:{vc_type}:{vc_value}@{ti_id}"
                    elif self.config.should_include_context("VC", "CWE") and cwe_id:
                        vc_id = f"VC:{vc_type}:{vc_value}@{cwe_id}"
                    elif self.config.should_include_context("VC", "CVE") and cve_id:
                        vc_id = f"VC:{vc_type}:{vc_value}@{cve_id}"
                    elif self.config.should_include_context("VC", "CPE") and cpe_id:
                        vc_id = f"VC:{vc_type}:{vc_value}@{cpe_id}"
                    elif self.config.should_include_context("VC", "HOST") and host_id:
                        vc_id = f"VC:{vc_type}:{vc_value}@{host_id}"
                    else:
                        # Universal (ATTACKER level)
                        vc_id = f"VC:{vc_type}:{vc_value}{layer_suffix}"

                    # Create the VC node if it doesn't exist
                    if not self.graph.has_node(vc_id):
                        node_attrs = {
                            "node_type": "VC",
                            "vc_type": vc_type,
                            "value": vc_value,
                            "layer": "L2" if is_layer_2 else "L1"
                        }
                        # EX:Y is the terminal goal - full system compromise
                        if vc_type == "EX" and vc_value == "Y":
                            node_attrs["is_terminal"] = True
                            node_attrs["label"] = "EXPLOITED"
                        # Store context IDs based on config
                        if self.config.should_include_context("VC", "HOST") and host_id:
                            node_attrs["host_id"] = host_id
                        if self.config.should_include_context("VC", "TI"):
                            node_attrs["ti_id"] = ti_id
                        self.graph.add_node(vc_id, **node_attrs)

                    # TI → VC (LEADS_TO edge - technical impact leads to this state change)
                    if not self.graph.has_edge(ti_id, vc_id):
                        self.graph.add_edge(
                            ti_id,
                            vc_id,
                            edge_type="LEADS_TO"
                        )
    
    # =========================================================================
    # BULK LOADING - 2-LAYER MODEL
    # =========================================================================
    
    def load_from_mock_data(self):
        """
        Load the complete graph from mock data using 2-layer model.

        Layer 1 (External): Initial attack from outside using AV:N CVEs
        INSIDE_NETWORK: Bridge state achieved after any compromise
        Layer 2 (Internal): Post-compromise using AV:A CVEs (full mesh)
        """
        # Build Layer 1 (external attack surface)
        self._build_layer(layer_suffix="")

        # Add Attacker entry point (connects to Layer 1 only)
        self._add_attacker_node()

        # Build Layer 2 (internal network, post-compromise)
        self._build_layer(layer_suffix=":INSIDE_NETWORK")

        # Create INSIDE_NETWORK bridge connecting Layer 1 EX:Y to Layer 2 hosts
        self._create_inside_network_bridge()

        # Wire multi-stage attacks: VC outcomes → CVE prerequisites
        # e.g., CVE1 yields PR:L → ENABLES → CVE2 requires PR:L
        self._wire_multistage_attacks()

    def load_from_data(self, data: "LoadedData"):
        """
        Load the complete graph from a LoadedData instance using 2-layer model.

        This method accepts data from any DataLoader implementation, enabling
        integration with real vulnerability scanners like Trivy.

        Args:
            data: LoadedData instance containing hosts, cpes, cves, cwes, etc.
        """
        # Store the data for use by layer building methods
        self._loaded_data = data

        # Build Layer 1 (external attack surface)
        self._build_layer(layer_suffix="")

        # Add Attacker entry point (connects to Layer 1 only)
        self._add_attacker_node()

        # Build Layer 2 (internal network, post-compromise)
        self._build_layer(layer_suffix=":INSIDE_NETWORK")

        # Create INSIDE_NETWORK bridge connecting Layer 1 EX:Y to Layer 2 hosts
        self._create_inside_network_bridge()

        # Wire multi-stage attacks: VC outcomes → CVE prerequisites
        self._wire_multistage_attacks()
    
    def _build_layer(self, layer_suffix: str = ""):
        """
        Build a layer of the attack graph.

        Args:
            layer_suffix: Suffix to add to node IDs (empty for Layer 1, ":INSIDE_NETWORK" for Layer 2)
        """
        # Use loaded data if available, otherwise fall back to mock data
        if self._loaded_data is not None:
            hosts = self._loaded_data.hosts
            cpes = self._loaded_data.cpes
            cves = self._loaded_data.cves
            cwes = self._loaded_data.cwes
            host_cpe_map = self._loaded_data.host_cpe_map
        else:
            from src.data.mock_data import (
                MOCK_HOSTS, MOCK_CPES, MOCK_CVES, MOCK_CWES,
                MOCK_HOST_CPE_MAP,
            )
            hosts = MOCK_HOSTS
            cpes = MOCK_CPES
            cves = MOCK_CVES
            cwes = MOCK_CWES
            host_cpe_map = MOCK_HOST_CPE_MAP

        is_layer_2 = layer_suffix != ""

        # Build lookup tables
        cpe_to_cves = {}
        for cve_data in cves:
            cpe_id = cve_data.get("cpe_id")
            if cpe_id:
                if cpe_id not in cpe_to_cves:
                    cpe_to_cves[cpe_id] = []
                cpe_to_cves[cpe_id].append(cve_data)

        cwe_lookup = {c["id"]: c for c in cwes}
        cpe_lookup = {c["id"]: c for c in cpes}

        # Add Hosts for this layer
        for host_data in hosts:
            host_id = f"{host_data['id']}{layer_suffix}"
            self.graph.add_node(
                host_id,
                node_type="HOST",
                label=host_data.get("hostname", host_data["id"]),
                subnet_id=host_data.get("subnet_id", ""),
                layer="L2" if is_layer_2 else "L1",
                original_id=host_data["id"]
            )
        
        # Process each host's software stack
        for original_host_id, cpe_ids in host_cpe_map.items():
            host_id = f"{original_host_id}{layer_suffix}"
            
            for cpe_id in cpe_ids:
                cpe_data = cpe_lookup.get(cpe_id)
                if not cpe_data:
                    continue
                
                # Create CPE node - can be grouped by ATTACKER (universal) or HOST
                if self.config.should_include_context("CPE", "HOST"):
                    actual_cpe_id = f"{cpe_id}@{host_id}"
                else:
                    actual_cpe_id = f"{cpe_id}{layer_suffix}"  # universal within layer

                if not self.graph.has_node(actual_cpe_id):
                    self.graph.add_node(
                        actual_cpe_id,
                        node_type="CPE",
                        original_cpe=cpe_id,
                        vendor=cpe_data["vendor"],
                        product=cpe_data["product"],
                        version=cpe_data["version"],
                        host_id=host_id if self.config.should_include_context("CPE", "HOST") else None,
                        layer="L2" if is_layer_2 else "L1"
                    )
                
                # Connect Host -> CPE
                if not self.graph.has_edge(host_id, actual_cpe_id):
                    self.add_edge(host_id, actual_cpe_id, EdgeType.RUNS)
                
                # Process CVEs for this CPE
                for cve_data in cpe_to_cves.get(cpe_id, []):
                    # CVE can be grouped by ATTACKER, HOST, or CPE
                    if self.config.is_universal("CVE"):
                        actual_cve_id = f"{cve_data['id']}{layer_suffix}"  # universal within layer
                    elif self.config.should_include_context("CVE", "CPE"):
                        actual_cve_id = f"{cve_data['id']}@{actual_cpe_id}"  # per-CPE
                    else:
                        actual_cve_id = f"{cve_data['id']}@{host_id}"  # per-HOST

                    if not self.graph.has_node(actual_cve_id):
                        self.graph.add_node(
                            actual_cve_id,
                            node_type="CVE",
                            original_cve=cve_data["id"],
                            description=cve_data["description"],
                            epss_score=cve_data["epss_score"],
                            cvss_vector=cve_data["cvss_vector"],
                            host_id=host_id if self.config.should_include_context("CVE", "HOST") else None,
                            cpe_id=actual_cpe_id if self.config.should_include_context("CVE", "CPE") else None,
                            layer="L2" if is_layer_2 else "L1"
                        )
                    
                    # CPE -> CVE
                    if not self.graph.has_edge(actual_cpe_id, actual_cve_id):
                        self.add_edge(actual_cpe_id, actual_cve_id, EdgeType.HAS_VULN)
                    
                    # Process CWE
                    original_cwe_id = cve_data.get("cwe_id")
                    if original_cwe_id:
                        cwe_info = cwe_lookup.get(original_cwe_id, {})
                        # CWE can be grouped by ATTACKER, HOST, CPE, or CVE
                        if self.config.is_universal("CWE"):
                            actual_cwe_id = f"{original_cwe_id}{layer_suffix}"  # universal within layer
                        elif self.config.should_include_context("CWE", "CVE"):
                            actual_cwe_id = f"{original_cwe_id}@{actual_cve_id}"  # per-CVE
                        elif self.config.should_include_context("CWE", "CPE"):
                            actual_cwe_id = f"{original_cwe_id}@{actual_cpe_id}"  # per-CPE
                        else:
                            actual_cwe_id = f"{original_cwe_id}@{host_id}"  # per-HOST

                        if not self.graph.has_node(actual_cwe_id):
                            self.graph.add_node(
                                actual_cwe_id,
                                node_type="CWE",
                                original_cwe=original_cwe_id,
                                name=cwe_info.get("name", original_cwe_id),
                                host_id=host_id if self.config.should_include_context("CWE", "HOST") else None,
                                layer="L2" if is_layer_2 else "L1"
                            )
                        
                        # CVE -> CWE
                        if not self.graph.has_edge(actual_cve_id, actual_cwe_id):
                            self.add_edge(actual_cve_id, actual_cwe_id, EdgeType.IS_INSTANCE_OF)
                        
                        # Wire CWE -> VCs (pass full context for VC ID construction)
                        self._wire_cwe_to_vcs(
                            actual_cwe_id,
                            host_id if self.config.should_include_context("VC", "HOST") else None,
                            actual_cpe_id if self.config.should_include_context("VC", "CPE") else None,
                            actual_cve_id if self.config.should_include_context("VC", "CVE") else None,
                            cve_data["cvss_vector"],
                            cve_data.get("technical_impacts", []),
                            layer_suffix
                        )
    
    def _create_inside_network_bridge(self):
        """
        Create INSIDE_NETWORK bridge connecting Layer 1 EX:Y nodes to Layer 2 hosts.

        Once any host is compromised (EX:Y in Layer 1), attacker is "inside the network"
        and can reach all hosts in Layer 2 with AV:A access.
        """
        # Use loaded data if available, otherwise fall back to mock data
        if self._loaded_data is not None:
            hosts = self._loaded_data.hosts
        else:
            from src.data.mock_data import MOCK_HOSTS
            hosts = MOCK_HOSTS

        # Create the central INSIDE_NETWORK node
        self.graph.add_node(
            "INSIDE_NETWORK",
            node_type="BRIDGE",
            label="INSIDE NETWORK",
            description="Attacker has penetrated the network perimeter",
            is_phase_separator=True
        )
        
        # Connect all Layer 1 EX:Y nodes to INSIDE_NETWORK
        for node_id, data in list(self.graph.nodes(data=True)):
            if (data.get("node_type") == "VC" and 
                data.get("vc_type") == "EX" and 
                data.get("value") == "Y" and
                data.get("layer") == "L1"):
                self.graph.add_edge(
                    node_id,
                    "INSIDE_NETWORK",
                    edge_type="ENTERS_NETWORK"
                )
        
        # Connect INSIDE_NETWORK to all Layer 2 hosts (full mesh)
        for host_data in hosts:
            layer2_host_id = f"{host_data['id']}:INSIDE_NETWORK"
            if self.graph.has_node(layer2_host_id):
                self.graph.add_edge(
                    "INSIDE_NETWORK",
                    layer2_host_id,
                    edge_type="CAN_REACH"
                )
    
    def _wire_multistage_attacks(self):
        """
        Create edges from VC outcomes to CVEs that require those VCs as prerequisites.
        
        This enables multi-stage attack chains:
        - CVE1 (AV:N, PR:N) → yields VC:PR:L
        - VC:PR:L → ENABLES → CVE2 (requires AV:L, PR:L)  # CVE2 != CVE1!
        - CVE2 → yields VC:EX:Y (terminal)
        
        IMPORTANT: A VC cannot ENABLE the CVE that produced it (no self-loops).
        
        VC Hierarchy (from paper):
        - AV: N < A < L < P (gaining L satisfies requirement for N, A, L)
        - PR: N < L < H (gaining H satisfies requirement for N, L, H)
        """
        from src.core.consensual_matrix import extract_prerequisites, AV_HIERARCHY, PR_HIERARCHY
        
        # Collect all CVE nodes with their prerequisites
        cve_nodes = []
        for node_id, data in self.graph.nodes(data=True):
            if data.get("node_type") == "CVE":
                cvss = data.get("cvss_vector", "")
                prereqs = extract_prerequisites(cvss)
                host_id = data.get("host_id")
                cve_nodes.append({
                    "id": node_id,
                    "host_id": host_id,
                    "prereqs": prereqs,  # List of (vc_type, vc_value)
                })
        
        # Collect all VC nodes AND track which CVEs produce them
        # by tracing: CVE → CPE → CWE → TI → VC path (via edges)
        vc_nodes = {}
        vc_producer_cves = {}  # vc_node_id → set of CVE IDs that produced this VC
        
        for node_id, data in self.graph.nodes(data=True):
            if data.get("node_type") == "VC":
                vc_type = data.get("vc_type")
                vc_value = data.get("value")
                host_id = data.get("host_id")
                key = (vc_type, vc_value, host_id)
                vc_nodes[key] = node_id
                
                # Track which CVEs produced this VC by tracing backwards
                # VC ← TI ← CWE ← CVE
                producer_cves = set()
                for ti_id in self.graph.predecessors(node_id):
                    ti_data = self.graph.nodes.get(ti_id, {})
                    if ti_data.get("node_type") == "TI":
                        for cwe_id in self.graph.predecessors(ti_id):
                            cwe_data = self.graph.nodes.get(cwe_id, {})
                            if cwe_data.get("node_type") == "CWE":
                                for cve_id in self.graph.predecessors(cwe_id):
                                    cve_data = self.graph.nodes.get(cve_id, {})
                                    if cve_data.get("node_type") == "CVE":
                                        producer_cves.add(cve_id)
                
                vc_producer_cves[node_id] = producer_cves
        
        # Determine what host context VC nodes use based on granularity config
        # When VC is universal (ATTACKER), VCs have host_id=None, so lookups
        # must use None too. Otherwise use the CVE's host_id.
        vc_includes_host = self.config.should_include_context("VC", "HOST")

        # For each CVE that requires specific VCs, find VCs that SATISFY those requirements
        # Using VC hierarchy: higher privilege satisfies lower privilege requirement
        for cve in cve_nodes:
            for vc_type, required_value in cve["prereqs"]:
                # Skip network access - attacker has this by default if host is reachable
                if vc_type == "AV" and required_value == "N":
                    continue
                if vc_type == "PR" and required_value == "N":
                    continue

                # Use the CVE's host_id only if VC nodes include host context
                lookup_host = cve["host_id"] if vc_includes_host else None

                # Find all VCs that SATISFY this requirement (same or higher privilege)
                satisfying_vcs = []

                if vc_type == "AV":
                    # AV hierarchy: N < A < L < P
                    # If CVE requires L, VCs with L or P satisfy it
                    required_level = AV_HIERARCHY.get(required_value, 0)
                    for av_value, level in AV_HIERARCHY.items():
                        if level >= required_level:
                            vc_key = ("AV", av_value, lookup_host)
                            if vc_key in vc_nodes:
                                satisfying_vcs.append(vc_nodes[vc_key])

                elif vc_type == "PR":
                    # PR hierarchy: N < L < H
                    # If CVE requires L, VCs with L or H satisfy it
                    required_level = PR_HIERARCHY.get(required_value, 0)
                    for pr_value, level in PR_HIERARCHY.items():
                        if level >= required_level:
                            vc_key = ("PR", pr_value, lookup_host)
                            if vc_key in vc_nodes:
                                satisfying_vcs.append(vc_nodes[vc_key])
                
                # Create ENABLES edges from satisfying VCs to this CVE
                # BUT NOT if this CVE produced that VC (no self-loops!)
                for vc_node_id in satisfying_vcs:
                    producer_cves = vc_producer_cves.get(vc_node_id, set())
                    
                    # Skip if this CVE produced this VC (would create self-loop)
                    if cve["id"] in producer_cves:
                        continue
                    
                    if not self.graph.has_edge(vc_node_id, cve["id"]):
                        self.graph.add_edge(
                            vc_node_id,
                            cve["id"],
                            edge_type="ENABLES"
                        )
    
    def _wire_cross_host_pivoting(self):
        """
        Create AV:A (Adjacent) nodes for other hosts when EX:Y is achieved.
        
        Cross-host pivoting logic:
        - When EX:Y is gained on host-A, attacker can pivot to adjacent hosts
        - Create AV:A node for each OTHER host
        - Connect: EX:Y@host-A → PIVOTS_TO → AV:A@host-B
        
        This enables multi-host attack chains where exploiting one host
        grants network adjacency to other hosts.
        """
        # Find all terminal EX:Y nodes
        ex_y_nodes = []
        for node_id, data in self.graph.nodes(data=True):
            if (data.get("node_type") == "VC" and 
                data.get("vc_type") == "EX" and 
                data.get("value") == "Y"):
                host_id = data.get("host_id")
                ex_y_nodes.append((node_id, host_id))
        
        # Find all host nodes
        all_hosts = set()
        for node_id, data in self.graph.nodes(data=True):
            if data.get("node_type") == "HOST":
                all_hosts.add(node_id)
        
        # For each EX:Y node, create AV:A for OTHER hosts
        for ex_node_id, source_host in ex_y_nodes:
            for target_host in all_hosts:
                # Skip the host where EX:Y was gained
                if target_host == source_host:
                    continue
                
                # Create AV:A node for target host
                av_a_id = f"VC:AV:A@{target_host}"
                
                if not self.graph.has_node(av_a_id):
                    self.graph.add_node(
                        av_a_id,
                        node_type="VC",
                        vc_type="AV",
                        value="A",
                        host_id=target_host,
                        is_pivot=True,  # Mark as pivot-created node
                        label=f"AV:A"
                    )
                
                # Connect EX:Y → PIVOTS_TO → AV:A
                if not self.graph.has_edge(ex_node_id, av_a_id):
                    self.graph.add_edge(
                        ex_node_id,
                        av_a_id,
                        edge_type="PIVOTS_TO"
                    )
    
    def _add_attacker_node(self):
        """
        Add an Attacker node with initial VCs in a compound box.
        
        The attacker starts with:
        - AV:N (Network access)
        - PR:N (No privileges needed)
        
        These are grouped in a visual box to show initial state.
        """
        # Create parent box (compound node)
        self.graph.add_node(
            "ATTACKER_BOX",
            node_type="COMPOUND",
            label="Initial State",
            description="Attacker's initial capabilities",
            is_compound=True
        )
        
        # Add the Attacker node as child of box
        self.graph.add_node(
            "ATTACKER",
            node_type="ATTACKER",
            label="Hacker",
            description="External threat actor with network access",
            parent="ATTACKER_BOX"
        )
        
        # Add initial VCs as children of the box
        self.graph.add_node(
            "VC:AV:N",
            node_type="VC",
            vc_type="AV",
            value="N",
            label="AV:N",
            description="Network access (can reach hosts from outside)",
            parent="ATTACKER_BOX",
            is_initial=True
        )
        
        self.graph.add_node(
            "VC:PR:N",
            node_type="VC",
            vc_type="PR",
            value="N",
            label="PR:N", 
            description="No privileges (unauthenticated access)",
            parent="ATTACKER_BOX",
            is_initial=True
        )
        
        # Connect initial VCs to attacker (VCs lead to attacker, showing initial capabilities)
        self.graph.add_edge("VC:AV:N", "ATTACKER", edge_type="HAS_STATE")
        self.graph.add_edge("VC:PR:N", "ATTACKER", edge_type="HAS_STATE")
        
        # Connect attacker to DMZ hosts (publicly accessible) in Layer 1 only
        dmz_hosts = [node_id for node_id, data in self.graph.nodes(data=True) 
                     if data.get("node_type") == "HOST" and 
                        data.get("subnet_id") == "dmz" and
                        data.get("layer") == "L1"]  # Only Layer 1 hosts
        
        for host_id in dmz_hosts:
            self.graph.add_edge(
                "ATTACKER",
                host_id,
                edge_type="CAN_REACH"
            )

    # =========================================================================
    # EXPORT / QUERY
    # =========================================================================
    
    def get_stats(self) -> Dict[str, int]:
        """Get graph statistics."""
        node_counts = {}
        for _, data in self.graph.nodes(data=True):
            nt = data.get("node_type", "unknown")
            node_counts[nt] = node_counts.get(nt, 0) + 1
        
        edge_counts = {}
        for _, _, data in self.graph.edges(data=True):
            et = data.get("edge_type", "unknown")
            edge_counts[et] = edge_counts.get(et, 0) + 1
        
        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "node_counts": node_counts,
            "edge_counts": edge_counts
        }
    
    def to_json(self) -> Dict:
        """Export graph as JSON for visualization."""
        nodes = []
        for node_id, data in self.graph.nodes(data=True):
            nodes.append({
                "id": node_id,
                **data
            })
        
        edges = []
        for source, target, data in self.graph.edges(data=True):
            edges.append({
                "source": source,
                "target": target,
                **data
            })
        
        return {
            "nodes": nodes,
            "edges": edges
        }
    
    def export_gexf(self, filepath: str):
        """Export graph to GEXF format for Gephi."""
        nx.write_gexf(self.graph, filepath)


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def build_knowledge_graph(config: GraphConfig = None) -> KnowledgeGraphBuilder:
    """Build and return a complete knowledge graph from mock data."""
    builder = KnowledgeGraphBuilder(config)
    builder.load_from_mock_data()
    return builder
