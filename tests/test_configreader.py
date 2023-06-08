"""Test the configreader module."""
from __future__ import annotations

from pathlib import Path

import pytest
from const import TEST_CONF_PATH_ERROR, TEST_CONF_PATH_NO_SEC, TEST_CONF_PATH_SEC, TEST_SECRETS_PATH
from pytz import UnknownTimeZoneError

from pvcast.config.configreader import ConfigReader


class TestConfigReader:
    """Test the configreader module."""

    @pytest.fixture
    def configreader_secfile_sectags(self):
        """Fixture for the configreader."""
        return ConfigReader(TEST_CONF_PATH_SEC, TEST_SECRETS_PATH)

    @pytest.fixture
    def configreader_no_secfile_no_sectags(self):
        """Fixture for the configreader initialized without a secrets file and no !secret tags in config."""
        return ConfigReader(config_file_path=TEST_CONF_PATH_NO_SEC)

    @pytest.fixture
    def configreader_no_secfile_sectags(self):
        """
        Fixture for the configreader initialized without a secrets file but with !secret tags in config.
        This should raise an exception.
        """
        return ConfigReader(config_file_path=TEST_CONF_PATH_SEC)

    @pytest.fixture
    def configreader_wrong_timezone(self):
        """
        Fixture for the configreader initialized with a timezone that does not exist.
        This should raise an exception.
        """
        return ConfigReader(config_file_path=TEST_CONF_PATH_ERROR)

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

    def test_configreader_wrong_config_file(self):
        """Test the configreader with a wrong config file."""
        with pytest.raises(FileNotFoundError):
            ConfigReader(Path("wrongfile.yaml")).config

    def test_invalid_timezone(self, configreader_wrong_timezone):
        """Test the configreader with an invalid timezone."""
        with pytest.raises(UnknownTimeZoneError):
            configreader_wrong_timezone.config
