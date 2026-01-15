"""
Tests for src/core/config.py - Graph configuration.
"""

import pytest
from src.core.config import GraphConfig, DuplicationMode, DEFAULT_CONFIG


class TestGraphConfigDefaults:
    """Tests for default configuration values."""
    
    def test_default_config_exists(self):
        """Verify DEFAULT_CONFIG is available."""
        assert DEFAULT_CONFIG is not None
        assert isinstance(DEFAULT_CONFIG, GraphConfig)
    
    def test_default_host_mode(self):
        """HOST should always be universal."""
        config = GraphConfig()
        assert config.node_modes["HOST"] == "universal"
    
    def test_default_singular_modes(self):
        """CPE, CVE, CWE, TI, VC should default to singular."""
        config = GraphConfig()
        for node_type in ["CPE", "CVE", "CWE", "TI", "VC"]:
            assert config.node_modes[node_type] == "singular"


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
        """Unknown types default to singular."""
        config = GraphConfig()
        assert config.is_singular("UNKNOWN") == True
    
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
        assert result["HOST"] == "universal"
    
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
