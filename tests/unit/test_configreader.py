"""Test the configreader module."""
from __future__ import annotations

from pathlib import Path

import pytest
from pytz import UnknownTimeZoneError
from yaml import YAMLError

from pvcast.config.configreader import ConfigReader

from ..const import (
    TEST_CONF_PATH_ERROR,
    TEST_CONF_PATH_NO_SEC,
    TEST_CONF_PATH_SEC,
    TEST_SECRETS_PATH,
    TEST_CONF_PATH_MISSING_SEC,
)


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

    def test_configreader_secrets_no_secrets_file(self):
        """Test the configreader with a secrets file but no secrets file path."""
        with pytest.raises(YAMLError):
            _ = ConfigReader(TEST_CONF_PATH_SEC).config

    def test_configreader_no_secrets(self, configreader_no_secfile_no_sectags):
        """Test the configreader without a secrets file and no !secret tags in config."""
        assert isinstance(configreader_no_secfile_no_sectags, ConfigReader)
        config = configreader_no_secfile_no_sectags.config
        print(config)
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

    def test_configreader_missing_secrets(self):
        """Test the configreader with a secrets file and !secret tags for which no entry in secrets.yaml exists."""
        with pytest.raises(YAMLError):
            ConfigReader(TEST_CONF_PATH_MISSING_SEC, TEST_SECRETS_PATH)

    def test_configreader_no_config_file(self):
        """Test the configreader without a config file."""
        with pytest.raises(TypeError):
            ConfigReader()

    def test_configreader_wrong_config_file(self):
        """Test the configreader with a wrong config file."""
        with pytest.raises(FileNotFoundError):
            ConfigReader(Path("wrongfile.yaml")).config

    def test_configreader_wrong_secrets_file(self):
        """Test the configreader with a wrong secrets file."""
        with pytest.raises(FileNotFoundError):
            ConfigReader(TEST_CONF_PATH_SEC, Path("wrongfile.yaml")).config

    def test_invalid_timezone(self):
        """Test the configreader with an invalid timezone."""
        with pytest.raises(UnknownTimeZoneError):
            _ = ConfigReader(config_file_path=TEST_CONF_PATH_ERROR)
