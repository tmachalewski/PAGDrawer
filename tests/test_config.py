"""
Tests for src/core/config.py - Graph configuration.
"""

import pytest
from src.core.config import (
    GraphConfig, DuplicationMode, DEFAULT_CONFIG,
    GROUPING_HIERARCHY, VALID_GROUPINGS
)


class TestGraphConfigDefaults:
    """Tests for default configuration values."""

    def test_default_config_exists(self):
        """Verify DEFAULT_CONFIG is available."""
        assert DEFAULT_CONFIG is not None
        assert isinstance(DEFAULT_CONFIG, GraphConfig)

    def test_default_host_mode(self):
        """HOST should always be universal (grouped by ATTACKER)."""
        config = GraphConfig()
        assert config.is_universal("HOST")
        assert config.get_grouping_level("HOST") == "ATTACKER"

    def test_default_singular_modes(self):
        """CPE, CVE, CWE, TI, VC should default to singular (per-parent)."""
        config = GraphConfig()
        for node_type in ["CPE", "CVE", "CWE", "TI", "VC"]:
            assert config.is_singular(node_type)


class TestGraphConfigMethods:
    """Tests for GraphConfig methods."""
    
    def test_is_singular(self):
        """Test is_singular method."""
        config = GraphConfig()
        assert config.is_singular("CPE") == True
        assert config.is_singular("HOST") == False
    
    def test_is_universal(self):
        """Test is_universal method."""
        config = GraphConfig()
        assert config.is_universal("HOST") == True
        assert config.is_universal("CVE") == False
    
    def test_is_singular_unknown_type(self):
        """Unknown types default to universal (ATTACKER grouping)."""
        config = GraphConfig()
        # Unknown types get ATTACKER grouping by default, which is universal
        assert config.is_universal("UNKNOWN") == True
    
    def test_set_mode(self):
        """Test set_mode method."""
        config = GraphConfig()
        config.set_mode("CPE", "universal")
        assert config.node_modes["CPE"] == "universal"
        assert config.is_universal("CPE") == True
    
    def test_set_mode_back_to_singular(self):
        """Test changing mode back to singular."""
        config = GraphConfig()
        config.set_mode("CPE", "universal")
        config.set_mode("CPE", "singular")
        assert config.is_singular("CPE") == True


class TestGraphConfigSerialization:
    """Tests for serialization/deserialization."""
    
    def test_to_dict(self):
        """Test to_dict export."""
        config = GraphConfig()
        result = config.to_dict()

        assert isinstance(result, dict)
        assert "HOST" in result
        assert "CPE" in result
        assert "TI" in result
        # HOST is grouped by ATTACKER (universal)
        assert result["HOST"] == "ATTACKER"
    
    def test_from_dict(self):
        """Test from_dict import."""
        data = {
            "HOST": "universal",
            "CPE": "universal",
            "CVE": "singular",
            "CWE": "singular",
            "TI": "singular",
            "VC": "singular"
        }
        config = GraphConfig.from_dict(data)
        
        assert config.is_universal("CPE") == True
        assert config.is_singular("CVE") == True
    
    def test_from_dict_ignores_invalid_modes(self):
        """Invalid mode values should be ignored."""
        data = {
            "CPE": "invalid_mode",
            "CVE": "singular"
        }
        config = GraphConfig.from_dict(data)
        
        # Invalid mode shouldn't be applied
        assert config.node_modes.get("CPE") != "invalid_mode"
        assert config.is_singular("CVE") == True
    
    def test_round_trip(self):
        """Test to_dict -> from_dict round trip."""
        original = GraphConfig()
        original.set_mode("CPE", "universal")
        original.set_mode("TI", "universal")
        
        exported = original.to_dict()
        restored = GraphConfig.from_dict(exported)
        
        assert restored.is_universal("CPE") == True
        assert restored.is_universal("TI") == True
        assert restored.is_singular("CVE") == True


class TestGetGroupingLevel:
    """Tests for get_grouping_level() method."""

    def test_default_grouping_levels(self):
        """Verify default grouping levels for each node type."""
        config = GraphConfig()
        assert config.get_grouping_level("HOST") == "ATTACKER"
        assert config.get_grouping_level("CPE") == "HOST"
        assert config.get_grouping_level("CVE") == "CPE"
        assert config.get_grouping_level("CWE") == "CVE"
        assert config.get_grouping_level("TI") == "CWE"
        assert config.get_grouping_level("VC") == "HOST"

    def test_grouping_level_with_legacy_universal(self):
        """Legacy 'universal' should map to 'ATTACKER'."""
        config = GraphConfig()
        config.set_mode("CPE", "universal")
        assert config.get_grouping_level("CPE") == "ATTACKER"

    def test_grouping_level_with_legacy_singular(self):
        """Legacy 'singular' should map to most granular level."""
        config = GraphConfig()
        config.set_mode("TI", "singular")
        # TI's most granular is CWE (last in VALID_GROUPINGS["TI"])
        assert config.get_grouping_level("TI") == "CWE"

    def test_grouping_level_with_granular_value(self):
        """Granular values should be returned as-is."""
        config = GraphConfig()
        config.set_mode("TI", "HOST")
        assert config.get_grouping_level("TI") == "HOST"

        config.set_mode("CVE", "ATTACKER")
        assert config.get_grouping_level("CVE") == "ATTACKER"

    def test_grouping_level_unknown_type(self):
        """Unknown types should return 'ATTACKER'."""
        config = GraphConfig()
        assert config.get_grouping_level("UNKNOWN") == "ATTACKER"


class TestShouldIncludeContext:
    """Tests for should_include_context() method."""

    def test_universal_includes_no_context(self):
        """When grouped by ATTACKER (universal), no context should be included."""
        config = GraphConfig()
        config.set_mode("CVE", "ATTACKER")

        assert config.should_include_context("CVE", "HOST") == False
        assert config.should_include_context("CVE", "CPE") == False

    def test_host_grouping_includes_host_only(self):
        """When grouped by HOST, only HOST context should be included."""
        config = GraphConfig()
        config.set_mode("CVE", "HOST")

        assert config.should_include_context("CVE", "HOST") == True
        assert config.should_include_context("CVE", "CPE") == False

    def test_cpe_grouping_includes_host_and_cpe(self):
        """When grouped by CPE, HOST and CPE context should be included."""
        config = GraphConfig()
        config.set_mode("CVE", "CPE")

        assert config.should_include_context("CVE", "HOST") == True
        assert config.should_include_context("CVE", "CPE") == True

    def test_ti_grouping_levels(self):
        """Test TI with various grouping levels."""
        config = GraphConfig()

        # TI grouped by HOST - include HOST only
        config.set_mode("TI", "HOST")
        assert config.should_include_context("TI", "HOST") == True
        assert config.should_include_context("TI", "CPE") == False
        assert config.should_include_context("TI", "CVE") == False
        assert config.should_include_context("TI", "CWE") == False

        # TI grouped by CVE - include HOST, CPE, CVE
        config.set_mode("TI", "CVE")
        assert config.should_include_context("TI", "HOST") == True
        assert config.should_include_context("TI", "CPE") == True
        assert config.should_include_context("TI", "CVE") == True
        assert config.should_include_context("TI", "CWE") == False

        # TI grouped by CWE (most granular) - include all
        config.set_mode("TI", "CWE")
        assert config.should_include_context("TI", "HOST") == True
        assert config.should_include_context("TI", "CPE") == True
        assert config.should_include_context("TI", "CVE") == True
        assert config.should_include_context("TI", "CWE") == True

    def test_invalid_context_type(self):
        """Invalid context types should return False."""
        config = GraphConfig()
        assert config.should_include_context("CVE", "INVALID") == False

    def test_context_after_grouping_level(self):
        """Context types after the grouping level should not be included."""
        config = GraphConfig()
        config.set_mode("CWE", "CPE")

        # CVE comes after CPE in hierarchy, so should not be included
        assert config.should_include_context("CWE", "CVE") == False


class TestGranularConfigRoundTrip:
    """Tests for granular config serialization."""

    def test_granular_values_persist(self):
        """Granular values should survive to_dict/from_dict round trip."""
        original = GraphConfig()
        original.set_mode("CPE", "ATTACKER")
        original.set_mode("CVE", "HOST")
        original.set_mode("CWE", "CPE")
        original.set_mode("TI", "CVE")

        exported = original.to_dict()
        restored = GraphConfig.from_dict(exported)

        assert restored.get_grouping_level("CPE") == "ATTACKER"
        assert restored.get_grouping_level("CVE") == "HOST"
        assert restored.get_grouping_level("CWE") == "CPE"
        assert restored.get_grouping_level("TI") == "CVE"

    def test_all_valid_groupings_accepted(self):
        """All valid grouping values should be accepted by from_dict."""
        for node_type, valid_levels in VALID_GROUPINGS.items():
            for level in valid_levels:
                data = {node_type: level}
                config = GraphConfig.from_dict(data)
                assert config.get_grouping_level(node_type) == level
