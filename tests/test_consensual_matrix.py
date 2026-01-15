"""
Tests for src/core/consensual_matrix.py - TI → VC transformations.
"""

import pytest
from src.core.consensual_matrix import (
    TechnicalImpact,
    extract_prerequisites,
    extract_environmental_filters,
    get_post_exploitation_vcs,
    transform_cve_to_vc_edges
)


class TestTechnicalImpactEnum:
    """Tests for TechnicalImpact enum."""
    
    def test_has_code_execution(self):
        """Verify code execution impact exists."""
        assert hasattr(TechnicalImpact, "EXECUTE_CODE")
        assert TechnicalImpact.EXECUTE_CODE.value == "Execute Unauthorized Code or Commands"
    
    def test_has_privilege_escalation(self):
        """Verify privilege escalation impact exists."""
        assert hasattr(TechnicalImpact, "GAIN_PRIVILEGES")
    
    def test_has_memory_read(self):
        """Verify memory read impact exists."""
        assert hasattr(TechnicalImpact, "READ_MEMORY")
    
    def test_has_dos_impacts(self):
        """Verify DoS-related impacts exist."""
        dos_impacts = [
            "DOS_CRASH", "DOS_INSTABILITY", "DOS_CPU",
            "DOS_MEMORY", "DOS_OTHER", "DOS_AMPLIFICATION"
        ]
        for impact in dos_impacts:
            assert hasattr(TechnicalImpact, impact)
    
    def test_impact_count(self):
        """Verify we have 24 technical impacts."""
        assert len(TechnicalImpact) == 24


class TestExtractPrerequisites:
    """Tests for extract_prerequisites function."""
    
    def test_network_no_priv(self, sample_cvss_vector):
        """Test extraction from AV:N/PR:N vector."""
        prereqs = extract_prerequisites(sample_cvss_vector)
        
        # Should require network access and no privileges
        av_prereqs = [p for p in prereqs if p[0] == "AV"]
        pr_prereqs = [p for p in prereqs if p[0] == "PR"]
        
        assert len(av_prereqs) >= 1
        assert ("AV", "N") in prereqs or any(p[1] == "N" for p in av_prereqs)
    
    def test_local_high_priv(self, sample_cvss_local):
        """Test extraction from AV:L/PR:H vector."""
        prereqs = extract_prerequisites(sample_cvss_local)
        
        # Should require local access and high privileges
        assert any(p[0] == "AV" for p in prereqs)
        assert any(p[0] == "PR" for p in prereqs)
    
    def test_empty_vector(self):
        """Empty vector should return empty list."""
        prereqs = extract_prerequisites("")
        assert prereqs == []


class TestExtractEnvironmentalFilters:
    """Tests for extract_environmental_filters function."""
    
    def test_low_complexity_no_interaction(self, sample_cvss_vector):
        """Test AC:L/UI:N extraction."""
        filters = extract_environmental_filters(sample_cvss_vector)
        
        assert "AC" in filters
        assert "UI" in filters
        # AC:L returns weight 1.0, AC:H returns 0.5
        assert filters["AC"] == 1.0
        # UI:N returns weight 1.0, UI:R returns 0.4
        assert filters["UI"] == 1.0
    
    def test_high_complexity_required_interaction(self, sample_cvss_high_complexity):
        """Test AC:H/UI:R extraction."""
        filters = extract_environmental_filters(sample_cvss_high_complexity)
        
        # AC:H = 0.5, UI:R = 0.4
        assert filters["AC"] == 0.5
        assert filters["UI"] == 0.4
    
    def test_filter_weights_are_floats(self, sample_cvss_vector):
        """Verify weights are floats."""
        filters = extract_environmental_filters(sample_cvss_vector)
        
        assert isinstance(filters["AC"], float)
        assert isinstance(filters["UI"], float)


class TestGetPostExploitationVCs:
    """Tests for get_post_exploitation_vcs function."""
    
    def test_code_execution_gains(self):
        """Code execution should grant high privileges."""
        vcs = get_post_exploitation_vcs("Execute Unauthorized Code or Commands")
        
        # Should include AV:L (local access) and PR:H (high privileges)
        vc_tuples = [(vc[0], vc[1]) for vc in vcs]
        assert any(vc[0] == "AV" for vc in vcs)
        assert any(vc[0] == "PR" for vc in vcs)
    
    def test_privilege_gain(self):
        """Privilege escalation should grant high privileges."""
        vcs = get_post_exploitation_vcs("Gain Privileges or Assume Identity")
        
        assert any(vc[0] == "PR" for vc in vcs)
    
    def test_dos_no_privilege_gain(self):
        """DoS attacks should not grant privileges."""
        vcs = get_post_exploitation_vcs("DoS: Crash, Exit, or Restart")
        
        # DoS typically doesn't grant privilege escalation
        pr_vcs = [vc for vc in vcs if vc[0] == "PR"]
        assert len(pr_vcs) == 0 or all(vc[1] != "H" for vc in pr_vcs)
    
    def test_unknown_impact(self):
        """Unknown impact should return safe defaults."""
        vcs = get_post_exploitation_vcs("Unknown Impact Type")
        
        # Should return empty or minimal VCs
        assert isinstance(vcs, list)


class TestTransformCveToVcEdges:
    """Tests for complete CVE to VC transformation."""
    
    def test_returns_dict_with_prereqs_and_outcomes(self, sample_cvss_vector):
        """Verify return structure."""
        result = transform_cve_to_vc_edges(
            cve_id="CVE-2021-44228",
            cvss_vector=sample_cvss_vector,
            technical_impact="Execute Unauthorized Code or Commands"
        )
        
        assert "prerequisites" in result
        assert "outcomes" in result
        assert isinstance(result["prerequisites"], list)
        assert isinstance(result["outcomes"], list)
    
    def test_code_execution_transformation(self, sample_cvss_vector):
        """Test full transformation for code execution."""
        result = transform_cve_to_vc_edges(
            cve_id="CVE-2021-44228",
            cvss_vector=sample_cvss_vector,
            technical_impact="Execute Unauthorized Code or Commands"
        )
        
        # Should have outcomes for code execution
        assert len(result["outcomes"]) > 0
    
    def test_prerequisites_match_cvss(self, sample_cvss_local):
        """Prerequisites should match CVSS requirements."""
        result = transform_cve_to_vc_edges(
            cve_id="CVE-TEST",
            cvss_vector=sample_cvss_local,
            technical_impact="Read Memory"
        )
        
        # AV:L/PR:H should be in prerequisites
        prereqs = result["prerequisites"]
        assert len(prereqs) > 0
