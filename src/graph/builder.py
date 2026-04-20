"""
Graph Builder - Assembles the Heterogeneous Knowledge Graph.

Constructs the full graph with:
- Host, CPE, CVE, CWE, VC nodes
- Static edges (RUNS, HAS_VULN, IS_INSTANCE_OF, CONNECTED_TO)
- Dynamic VC edges (ALLOWS_EXPLOIT, YIELDS_STATE)
- Chain-depth-aware multi-stage attack wiring (BFS)
"""

from typing import Dict, List, Optional, Any, Tuple, Set, TYPE_CHECKING
import networkx as nx

if TYPE_CHECKING:
    from src.data.loaders import LoadedData

from src.core.schema import (
    NodeType, EdgeType, VCType,
    HostNode, CPENode, CVENode, CWENode, VCNode, Edge,
    create_vc_id, parse_cvss_vector
)
from src.data.loaders.cwe_fetcher import STATIC_CWE_MAPPING
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
        layer_suffix: str = "",
        chain_depth: int = 0
    ) -> List[Tuple[str, str, str]]:
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
            layer_suffix: Suffix for layer identification
            chain_depth: Attack chain depth (0 = directly exploitable)

        Returns:
            List of (vc_type, vc_value, vc_node_id) tuples for VCs created
        """
        from src.core.consensual_matrix import (
            AV_HIERARCHY, PR_HIERARCHY, transform_cve_to_vc_edges
        )

        vc_info: List[Tuple[str, str, str]] = []

        # Skip if no technical impacts
        if not technical_impacts:
            return vc_info

        is_layer_2 = layer_suffix != ""
        depth_suffix = f":d{chain_depth}"

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

            # Create TI node (Technical Impact) with chain depth
            ti_label = technical_impact

            if self.config.is_universal("TI"):
                ti_id = f"TI:{technical_impact}{depth_suffix}{layer_suffix}"
            elif self.config.should_include_context("TI", "CWE"):
                ti_id = f"TI:{technical_impact}{depth_suffix}@{cwe_id}"
            else:
                ti_id = f"TI:{technical_impact}{depth_suffix}@{host_id}"

            if not self.graph.has_node(ti_id):
                self.graph.add_node(
                    ti_id,
                    node_type="TI",
                    impact=technical_impact,
                    label=ti_label,
                    description=f"Technical Impact: {technical_impact}",
                    layer="L2" if is_layer_2 else "L1",
                    host_id=host_id if self.config.should_include_context("TI", "HOST") else None,
                    cwe_id=cwe_id if self.config.should_include_context("TI", "CWE") else None,
                    chain_depth=chain_depth
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
                    # Determine VC ID based on config with chain depth
                    if self.config.should_include_context("VC", "TI"):
                        vc_node_id = f"VC:{vc_type}:{vc_value}{depth_suffix}@{ti_id}"
                    elif self.config.should_include_context("VC", "CWE") and cwe_id:
                        vc_node_id = f"VC:{vc_type}:{vc_value}{depth_suffix}@{cwe_id}"
                    elif self.config.should_include_context("VC", "CVE") and cve_id:
                        vc_node_id = f"VC:{vc_type}:{vc_value}{depth_suffix}@{cve_id}"
                    elif self.config.should_include_context("VC", "CPE") and cpe_id:
                        vc_node_id = f"VC:{vc_type}:{vc_value}{depth_suffix}@{cpe_id}"
                    elif self.config.should_include_context("VC", "HOST") and host_id:
                        vc_node_id = f"VC:{vc_type}:{vc_value}{depth_suffix}@{host_id}"
                    else:
                        # Universal (ATTACKER level)
                        vc_node_id = f"VC:{vc_type}:{vc_value}{depth_suffix}{layer_suffix}"

                    # Create the VC node if it doesn't exist
                    if not self.graph.has_node(vc_node_id):
                        node_attrs = {
                            "node_type": "VC",
                            "vc_type": vc_type,
                            "value": vc_value,
                            "layer": "L2" if is_layer_2 else "L1",
                            "chain_depth": chain_depth
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
                        self.graph.add_node(vc_node_id, **node_attrs)

                    # TI → VC (LEADS_TO edge)
                    if not self.graph.has_edge(ti_id, vc_node_id):
                        self.graph.add_edge(
                            ti_id,
                            vc_node_id,
                            edge_type="LEADS_TO"
                        )

                    vc_info.append((vc_type, vc_value, vc_node_id))

        return vc_info

    # =========================================================================
    # BULK LOADING - 2-LAYER MODEL WITH CHAIN DEPTH BFS
    # =========================================================================

    def load_from_mock_data(self):
        """
        Load the complete graph from mock data using 2-layer model
        with chain-depth-aware multi-stage attack wiring.

        If config.skip_layer_2 is True, only Layer 1 (external attack surface)
        is built. The INSIDE_NETWORK bridge is still created as a terminal node
        so that EX:Y → INSIDE_NETWORK edges are preserved.
        """
        # Phase 1: Build infrastructure + collect CVE entries for L1
        l1_entries = self._build_layer_infrastructure(layer_suffix="")

        # Add Attacker entry point
        self._add_attacker_node()

        # Phase 2: BFS chain building for L1
        initial_vcs_l1 = {("AV", "N"), ("PR", "N")}
        self._build_attack_chains_bfs(l1_entries, "", initial_vcs_l1)

        if self.config.skip_layer_2:
            # Single-layer mode: only create bridge node + ENTERS_NETWORK edges
            self._create_inside_network_bridge()
            return

        # Phase 3: L2 infrastructure
        l2_entries = self._build_layer_infrastructure(layer_suffix=":INSIDE_NETWORK")

        # Bridge L1 → L2
        self._create_inside_network_bridge()

        # Phase 4: BFS chain building for L2
        # L2 initial VCs = all VCs gained in L1 + AV:A from bridge
        l2_initial = self._collect_gained_vc_values("L1")
        l2_initial.add(("AV", "A"))
        self._build_attack_chains_bfs(l2_entries, ":INSIDE_NETWORK", l2_initial)

    def load_from_data(self, data: "LoadedData"):
        """
        Load the complete graph from a LoadedData instance using 2-layer model
        with chain-depth-aware multi-stage attack wiring.

        If config.skip_layer_2 is True, only Layer 1 (external attack surface)
        is built. The INSIDE_NETWORK bridge is still created as a terminal node.
        """
        self._loaded_data = data

        # Phase 1: Build infrastructure + collect CVE entries for L1
        l1_entries = self._build_layer_infrastructure(layer_suffix="")

        # Add Attacker entry point
        self._add_attacker_node()

        # Phase 2: BFS chain building for L1
        initial_vcs_l1 = {("AV", "N"), ("PR", "N")}
        self._build_attack_chains_bfs(l1_entries, "", initial_vcs_l1)

        if self.config.skip_layer_2:
            # Single-layer mode: only create bridge node + ENTERS_NETWORK edges
            self._create_inside_network_bridge()
            return

        # Phase 3: L2 infrastructure
        l2_entries = self._build_layer_infrastructure(layer_suffix=":INSIDE_NETWORK")

        # Bridge L1 → L2
        self._create_inside_network_bridge()

        # Phase 4: BFS chain building for L2
        l2_initial = self._collect_gained_vc_values("L1")
        l2_initial.add(("AV", "A"))
        self._build_attack_chains_bfs(l2_entries, ":INSIDE_NETWORK", l2_initial)

    def _get_data_source(self):
        """Get the data source (loaded data or mock data)."""
        if self._loaded_data is not None:
            return {
                "hosts": self._loaded_data.hosts,
                "cpes": self._loaded_data.cpes,
                "cves": self._loaded_data.cves,
                "cwes": self._loaded_data.cwes,
                "host_cpe_map": self._loaded_data.host_cpe_map,
            }
        else:
            from src.data.mock_data import (
                MOCK_HOSTS, MOCK_CPES, MOCK_CVES, MOCK_CWES,
                MOCK_HOST_CPE_MAP,
            )
            return {
                "hosts": MOCK_HOSTS,
                "cpes": MOCK_CPES,
                "cves": MOCK_CVES,
                "cwes": MOCK_CWES,
                "host_cpe_map": MOCK_HOST_CPE_MAP,
            }

    def _build_layer_infrastructure(self, layer_suffix: str = "") -> List[Dict]:
        """
        Build HOST and CPE nodes for a layer. Collect CVE entries for BFS.

        Returns:
            List of CVE entry dicts for BFS processing. Each entry contains:
            - cve_data: raw CVE dict
            - actual_cpe_id: computed CPE node ID
            - host_id: host node ID (with layer suffix)
            - cwe_lookup: CWE info dict
            - layer_suffix: layer suffix string
            - is_layer_2: bool
        """
        data = self._get_data_source()
        hosts = data["hosts"]
        cpes = data["cpes"]
        cves = data["cves"]
        cwes = data["cwes"]
        host_cpe_map = data["host_cpe_map"]

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

        # Build CPE nodes and collect CVE entries
        cve_entries = []

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
                    actual_cpe_id = f"{cpe_id}{layer_suffix}"

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

                # Collect CVE entries for BFS (don't create CVE nodes yet)
                for cve_data in cpe_to_cves.get(cpe_id, []):
                    cve_entries.append({
                        "cve_data": cve_data,
                        "actual_cpe_id": actual_cpe_id,
                        "host_id": host_id,
                        "cwe_lookup": cwe_lookup,
                        "layer_suffix": layer_suffix,
                        "is_layer_2": is_layer_2,
                    })

        return cve_entries

    # =========================================================================
    # BFS CHAIN-DEPTH ATTACK WIRING
    # =========================================================================

    def _build_attack_chains_bfs(
        self,
        cve_entries: List[Dict],
        layer_suffix: str,
        initial_vcs: Set[Tuple[str, str]]
    ):
        """
        BFS: assign chain depths and build CVE→CWE→TI→VC chains.

        Depth 0: CVEs whose AV/PR prerequisites are met by initial_vcs
        Depth N: CVEs whose prerequisites are met by VCs gained at depth < N
        Unreachable CVEs are not created (hidden).

        ENABLES edges connect VCs at depth N to CVEs at depth N+1.
        No self-loop check needed — depth ordering guarantees acyclicity.
        """
        from src.core.consensual_matrix import extract_prerequisites

        unprocessed = list(cve_entries)
        available_vcs = set(initial_vcs)
        max_depth = 10

        # Track VC nodes and CVE nodes created at each depth
        vc_nodes_by_depth: Dict[int, List[str]] = {}
        cve_nodes_by_depth: Dict[int, List[str]] = {}

        depth = 0
        while unprocessed and depth <= max_depth:
            newly_assigned = []
            still_unprocessed = []

            for entry in unprocessed:
                cvss = entry["cve_data"]["cvss_vector"]
                prereqs = extract_prerequisites(cvss)
                if self._prereqs_satisfied(prereqs, available_vcs):
                    entry["chain_depth"] = depth
                    newly_assigned.append(entry)
                else:
                    still_unprocessed.append(entry)

            if not newly_assigned:
                break

            # Build CVE→CWE→TI→VC chains for this depth
            new_vc_values: Set[Tuple[str, str]] = set()
            depth_vc_nodes: List[str] = []
            depth_cve_nodes: List[str] = []

            for entry in newly_assigned:
                cve_node_id, vc_results = self._build_cve_chain(entry)
                if cve_node_id:
                    depth_cve_nodes.append(cve_node_id)
                for vc_type, vc_value, vc_node_id in vc_results:
                    new_vc_values.add((vc_type, vc_value))
                    depth_vc_nodes.append(vc_node_id)

            vc_nodes_by_depth[depth] = depth_vc_nodes
            cve_nodes_by_depth[depth] = depth_cve_nodes

            # Wire ENABLES edges from previous depths' VCs to this depth's CVEs
            if depth > 0:
                self._wire_enables_for_depth(
                    depth, vc_nodes_by_depth, cve_nodes_by_depth
                )

            available_vcs.update(new_vc_values)
            unprocessed = still_unprocessed
            depth += 1

    def _prereqs_satisfied(
        self,
        prereqs: List[Tuple[str, str]],
        available_vcs: Set[Tuple[str, str]]
    ) -> bool:
        """Check if all AV/PR prerequisites are met by available VCs (using hierarchy)."""
        from src.core.consensual_matrix import AV_HIERARCHY, PR_HIERARCHY

        for vc_type, required_value in prereqs:
            # AC/UI are graph-wide constants, skip them
            if vc_type not in ("AV", "PR"):
                continue

            if vc_type == "AV":
                required_level = AV_HIERARCHY.get(required_value, 0)
                satisfied = any(
                    AV_HIERARCHY.get(v, 0) >= required_level
                    for t, v in available_vcs if t == "AV"
                )
            elif vc_type == "PR":
                required_level = PR_HIERARCHY.get(required_value, 0)
                satisfied = any(
                    PR_HIERARCHY.get(v, 0) >= required_level
                    for t, v in available_vcs if t == "PR"
                )
            else:
                satisfied = True

            if not satisfied:
                return False

        return True

    def _build_cve_chain(
        self, entry: Dict
    ) -> Tuple[Optional[str], List[Tuple[str, str, str]]]:
        """
        Build CVE→CWE→TI→VC chain for a single CVE entry at its assigned depth.

        Returns:
            (cve_node_id, [(vc_type, vc_value, vc_node_id), ...])
        """
        chain_depth = entry["chain_depth"]
        depth_suffix = f":d{chain_depth}"
        cve_data = entry["cve_data"]
        actual_cpe_id = entry["actual_cpe_id"]
        host_id = entry["host_id"]
        cwe_lookup = entry["cwe_lookup"]
        layer_suffix = entry["layer_suffix"]
        is_layer_2 = entry["is_layer_2"]

        # --- CVE node with depth ---
        if self.config.is_universal("CVE"):
            actual_cve_id = f"{cve_data['id']}{depth_suffix}{layer_suffix}"
        elif self.config.should_include_context("CVE", "CPE"):
            actual_cve_id = f"{cve_data['id']}{depth_suffix}@{actual_cpe_id}"
        else:
            actual_cve_id = f"{cve_data['id']}{depth_suffix}@{host_id}"

        if not self.graph.has_node(actual_cve_id):
            # Parse CVSS prerequisites for frontend merge-by-prereqs
            cvss_parts = {}
            for part in (cve_data["cvss_vector"] or "").split("/"):
                if ":" in part:
                    k, v = part.split(":", 1)
                    cvss_parts[k] = v
            prereqs = {
                "AV": cvss_parts.get("AV", "N"),
                "AC": cvss_parts.get("AC", "L"),
                "PR": cvss_parts.get("PR", "N"),
                "UI": cvss_parts.get("UI", "N"),
            }

            self.graph.add_node(
                actual_cve_id,
                node_type="CVE",
                original_cve=cve_data["id"],
                description=cve_data["description"],
                epss_score=cve_data["epss_score"],
                cvss_vector=cve_data["cvss_vector"],
                prereqs=prereqs,
                host_id=host_id if self.config.should_include_context("CVE", "HOST") else None,
                cpe_id=actual_cpe_id if self.config.should_include_context("CVE", "CPE") else None,
                layer="L2" if is_layer_2 else "L1",
                chain_depth=chain_depth
            )

        # CPE → CVE edge
        if not self.graph.has_edge(actual_cpe_id, actual_cve_id):
            self.add_edge(actual_cpe_id, actual_cve_id, EdgeType.HAS_VULN)

        # --- Process CWEs ---
        original_cwe_ids = cve_data.get("cwe_ids", [])
        if not original_cwe_ids and cve_data.get("cwe_id"):
            original_cwe_ids = [cve_data["cwe_id"]]

        all_vc_info: List[Tuple[str, str, str]] = []

        for original_cwe_id in original_cwe_ids:
            cwe_info = cwe_lookup.get(original_cwe_id, {})

            # CWE node with depth
            if self.config.is_universal("CWE"):
                actual_cwe_id = f"{original_cwe_id}{depth_suffix}{layer_suffix}"
            elif self.config.should_include_context("CWE", "CVE"):
                actual_cwe_id = f"{original_cwe_id}{depth_suffix}@{actual_cve_id}"
            elif self.config.should_include_context("CWE", "CPE"):
                actual_cwe_id = f"{original_cwe_id}{depth_suffix}@{actual_cpe_id}"
            else:
                actual_cwe_id = f"{original_cwe_id}{depth_suffix}@{host_id}"

            if not self.graph.has_node(actual_cwe_id):
                self.graph.add_node(
                    actual_cwe_id,
                    node_type="CWE",
                    original_cwe=original_cwe_id,
                    name=cwe_info.get("name", original_cwe_id),
                    host_id=host_id if self.config.should_include_context("CWE", "HOST") else None,
                    layer="L2" if is_layer_2 else "L1",
                    chain_depth=chain_depth
                )

            # CVE → CWE edge
            if not self.graph.has_edge(actual_cve_id, actual_cwe_id):
                self.add_edge(actual_cve_id, actual_cwe_id, EdgeType.IS_INSTANCE_OF)

            # Get TI impacts specific to this CWE
            cwe_technical_impacts = STATIC_CWE_MAPPING.get(original_cwe_id, [])
            if not cwe_technical_impacts:
                cwe_technical_impacts = cve_data.get("technical_impacts", [])

            # Wire CWE → TI → VC chain (returns VC info)
            vc_info = self._wire_cwe_to_vcs(
                actual_cwe_id,
                host_id if self.config.should_include_context("VC", "HOST") else None,
                actual_cpe_id if self.config.should_include_context("VC", "CPE") else None,
                actual_cve_id if self.config.should_include_context("VC", "CVE") else None,
                cve_data["cvss_vector"],
                cwe_technical_impacts,
                layer_suffix,
                chain_depth=chain_depth
            )
            all_vc_info.extend(vc_info)

        # Store VC outcomes for frontend merge-by-outcomes
        vc_outcomes = sorted(set((vt, vv) for vt, vv, _ in all_vc_info))
        self.graph.nodes[actual_cve_id]["vc_outcomes"] = [
            list(pair) for pair in vc_outcomes
        ]

        return actual_cve_id, all_vc_info

    def _wire_enables_for_depth(
        self,
        target_depth: int,
        vc_nodes_by_depth: Dict[int, List[str]],
        cve_nodes_by_depth: Dict[int, List[str]]
    ):
        """
        Wire ENABLES edges from VCs at depths < target_depth to CVEs at target_depth.

        Uses VC hierarchy: PR:H satisfies PR:L requirement, AV:L satisfies AV:L, etc.
        No self-loop check needed — depth ordering guarantees acyclicity.
        """
        from src.core.consensual_matrix import extract_prerequisites, AV_HIERARCHY, PR_HIERARCHY

        vc_includes_host = self.config.should_include_context("VC", "HOST")

        # Collect source VCs from all depths < target_depth, organized by key
        source_vcs: Dict[Tuple, List[str]] = {}
        for d in range(target_depth):
            for vc_node_id in vc_nodes_by_depth.get(d, []):
                vc_data = self.graph.nodes[vc_node_id]
                key = (vc_data.get("vc_type"), vc_data.get("value"), vc_data.get("host_id"))
                source_vcs.setdefault(key, []).append(vc_node_id)

        # For each target CVE, find satisfying source VCs
        for cve_id in cve_nodes_by_depth.get(target_depth, []):
            cve_data = self.graph.nodes[cve_id]
            cvss = cve_data.get("cvss_vector", "")
            prereqs = extract_prerequisites(cvss)
            cve_host_id = cve_data.get("host_id")

            lookup_host = cve_host_id if vc_includes_host else None

            for vc_type, required_value in prereqs:
                # Skip base-level access (attacker has these by default)
                if vc_type == "AV" and required_value == "N":
                    continue
                if vc_type == "PR" and required_value == "N":
                    continue

                satisfying_vc_nodes = []

                if vc_type == "AV":
                    required_level = AV_HIERARCHY.get(required_value, 0)
                    for av_value, level in AV_HIERARCHY.items():
                        if level >= required_level:
                            key = ("AV", av_value, lookup_host)
                            satisfying_vc_nodes.extend(source_vcs.get(key, []))
                elif vc_type == "PR":
                    required_level = PR_HIERARCHY.get(required_value, 0)
                    for pr_value, level in PR_HIERARCHY.items():
                        if level >= required_level:
                            key = ("PR", pr_value, lookup_host)
                            satisfying_vc_nodes.extend(source_vcs.get(key, []))

                for vc_node_id in satisfying_vc_nodes:
                    if not self.graph.has_edge(vc_node_id, cve_id):
                        self.graph.add_edge(
                            vc_node_id,
                            cve_id,
                            edge_type="ENABLES"
                        )

    def _collect_gained_vc_values(self, layer: str) -> Set[Tuple[str, str]]:
        """Collect (vc_type, vc_value) pairs from all VC nodes in a layer."""
        vcs: Set[Tuple[str, str]] = set()
        for _, data in self.graph.nodes(data=True):
            if data.get("node_type") == "VC" and data.get("layer") == layer:
                vcs.add((data.get("vc_type"), data.get("value")))
        return vcs

    # =========================================================================
    # BRIDGE AND ATTACKER
    # =========================================================================

    def _create_inside_network_bridge(self):
        """
        Create INSIDE_NETWORK bridge connecting Layer 1 EX:Y nodes to Layer 2 hosts.

        Once any host is compromised (EX:Y in Layer 1), attacker is "inside the network"
        and can reach all hosts in Layer 2 with AV:A access.
        """
        data = self._get_data_source()
        hosts = data["hosts"]

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

    def _wire_cross_host_pivoting(self):
        """
        Create AV:A (Adjacent) nodes for other hosts when EX:Y is achieved.

        Cross-host pivoting logic:
        - When EX:Y is gained on host-A, attacker can pivot to adjacent hosts
        - Create AV:A node for each OTHER host
        - Connect: EX:Y@host-A → PIVOTS_TO → AV:A@host-B
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
                if target_host == source_host:
                    continue

                av_a_id = f"VC:AV:A@{target_host}"

                if not self.graph.has_node(av_a_id):
                    self.graph.add_node(
                        av_a_id,
                        node_type="VC",
                        vc_type="AV",
                        value="A",
                        host_id=target_host,
                        is_pivot=True,
                        label=f"AV:A"
                    )

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

        UI and AC VCs are managed by the frontend's environment settings
        panel, not created here, to avoid duplicate nodes.

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

        # Add initial VCs as children of the box (state mutators only)
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

        # Connect initial VCs to attacker (showing initial capabilities)
        # Note: UI and AC VCs are created by the frontend environment settings
        self.graph.add_edge("VC:AV:N", "ATTACKER", edge_type="HAS_STATE")
        self.graph.add_edge("VC:PR:N", "ATTACKER", edge_type="HAS_STATE")

        # Connect attacker to DMZ hosts (publicly accessible) in Layer 1 only
        dmz_hosts = [node_id for node_id, data in self.graph.nodes(data=True)
                     if data.get("node_type") == "HOST" and
                        data.get("subnet_id") == "dmz" and
                        data.get("layer") == "L1"]

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
        """Export graph to GEXF format for Gephi.

        Strips attributes that GEXF can't serialize (dicts, nested lists).
        """
        # GEXF only supports scalar and flat-list attributes
        clean = self.graph.copy()
        for _, data in clean.nodes(data=True):
            for key in list(data.keys()):
                if isinstance(data[key], (dict, set)):
                    del data[key]
                elif isinstance(data[key], list) and data[key] and isinstance(data[key][0], (list, dict)):
                    del data[key]
        nx.write_gexf(clean, filepath)


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def build_knowledge_graph(config: GraphConfig = None) -> KnowledgeGraphBuilder:
    """Build and return a complete knowledge graph from mock data."""
    builder = KnowledgeGraphBuilder(config)
    builder.load_from_mock_data()
    return builder
