"""Test the configreader module."""
from __future__ import annotations

import pytest

from pvcast.config.configreader import ConfigReader


class TestConfigReader:
    """Test the configreader module."""

    def test_configreader_no_secrets(self, configreader_no_secfile_no_sectags):
        """Test the configreader without a secrets file and no !secret tags in config."""
        assert isinstance(configreader_no_secfile_no_sectags, ConfigReader)
        config = configreader_no_secfile_no_sectags.config
        assert isinstance(config, dict)
        assert config["plant"][0]["name"] == "EastWest"
        assert config["plant"][1]["name"] == "NorthSouth"

    def test_configreader_secrets(self, configreader_secfile_sectags):
        """Test the configreader with a secrets file and !secret tags in config."""
        assert isinstance(configreader_secfile_sectags, ConfigReader)
        config = configreader_secfile_sectags.config
        assert isinstance(config, dict)
        assert config["plant"][0]["name"] == "EastWest"
        assert config["plant"][1]["name"] == "NorthSouth"

    def test_configreader_no_secrets_sectags(self, configreader_no_secfile_sectags):
        """
        Test the configreader without a secrets file and !secret tags in config.
        This should raise a ValueError exception.
        """
        with pytest.raises(ValueError):
            configreader_no_secfile_sectags.config

    def test_configreader_no_config_file(self):
        """Test the configreader without a config file."""
        with pytest.raises(TypeError):
            ConfigReader()