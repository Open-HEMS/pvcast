"""Test the configreader module."""
from __future__ import annotations

from pathlib import Path

import pytest
from pytz import UnknownTimeZoneError
from yaml import ScalarNode, SequenceNode, YAMLError
from yaml.loader import SafeLoader

from pvcast.config.configreader import ConfigReader
from tests.const import (
    TEST_CONF_PATH_ERROR,
    TEST_CONF_PATH_MISSING_SEC,
    TEST_CONF_PATH_NO_SEC,
    TEST_CONF_PATH_SEC,
    TEST_SECRETS_PATH,
)


class TestConfigReader:
    """Test the configreader module."""

    @pytest.fixture
    def configreader_secfile_sectags(self) -> ConfigReader:
        """Fixture for the configreader."""
        return ConfigReader(TEST_CONF_PATH_SEC, TEST_SECRETS_PATH)

    @pytest.fixture
    def configreader_no_secfile_no_sectags(self) -> ConfigReader:
        """Fixture for the configreader initialized without a secrets file and no !secret tags in config."""
        return ConfigReader(TEST_CONF_PATH_NO_SEC)

    def test_configreader_no_secrets(
        self, configreader_no_secfile_no_sectags: ConfigReader
    ) -> None:
        """Test the configreader without a secrets file and no !secret tags in config."""
        assert isinstance(configreader_no_secfile_no_sectags, ConfigReader)
        config = configreader_no_secfile_no_sectags.config
        if not isinstance(config, dict):
            msg = "Config must be a dictionary."
            raise TypeError(msg)
        plant_config = config.get("plant")
        if not isinstance(plant_config, list):
            msg = "Plant config must be a list."
            raise TypeError(msg)
        assert config["plant"][0]["name"] == "EastWest"
        assert config["plant"][1]["name"] == "NorthSouth"

    def test_configreader_load_secrets_none(self) -> None:
        """Test the _load_secrets_file method with None as secrets file path."""
        configreader = ConfigReader(TEST_CONF_PATH_NO_SEC, None)
        with pytest.raises(ValueError, match="Secrets file path is not set."):
            configreader._load_secrets_file()

    def test_configreader_secrets(
        self, configreader_secfile_sectags: ConfigReader
    ) -> None:
        """Test the configreader with a secrets file and !secret tags in config."""
        assert isinstance(configreader_secfile_sectags, ConfigReader)
        config = configreader_secfile_sectags.config
        if not isinstance(config, dict):
            msg = "Config must be a dictionary."
            raise TypeError(msg)
        plant_config = config.get("plant")
        if not isinstance(plant_config, list):
            msg = "Plant config must be a list."
            raise TypeError(msg)
        assert config["plant"][0]["name"] == "EastWest"
        assert config["plant"][1]["name"] == "NorthSouth"

    def test_configreader_missing_secrets(self) -> None:
        """Test the configreader with a secrets file and !secret tags for which no entry in secrets.yaml exists."""
        with pytest.raises(YAMLError):
            ConfigReader(TEST_CONF_PATH_MISSING_SEC, TEST_SECRETS_PATH)

    def test_configreader_no_config_file(self) -> None:
        """Test the configreader without a config file."""
        with pytest.raises(TypeError):
            ConfigReader()  # type: ignore[call-arg]

    def test_configreader_wrong_config_file(self) -> None:
        """Test the configreader with a wrong config file."""
        with pytest.raises(FileNotFoundError):
            ConfigReader(Path("wrongfile.yaml"))

    def test_configreader_wrong_secrets_file(self) -> None:
        """Test the configreader with a wrong secrets file."""
        with pytest.raises(FileNotFoundError):
            ConfigReader(TEST_CONF_PATH_SEC, Path("wrongfile.yaml"))

    def test_invalid_timezone(self) -> None:
        """Test the configreader with an invalid timezone."""
        with pytest.raises(UnknownTimeZoneError):
            _ = ConfigReader(config_file_path=TEST_CONF_PATH_ERROR)

    def test_yaml_secrets_loader_scalar_node(
        self, configreader_secfile_sectags: ConfigReader
    ) -> None:
        """Test the _yaml_secrets_loader method with a ScalarNode."""
        loader = SafeLoader("")
        node = ScalarNode(tag="tag:yaml.org,2002:str", value="test_key")
        configreader_secfile_sectags._secrets = {"test_key": "test_value"}  # type: ignore[dict-item]
        assert (
            configreader_secfile_sectags._yaml_secrets_loader(loader, node)
            == "test_value"
        )

    def test_yaml_secrets_loader_non_scalar_node(
        self, configreader_secfile_sectags: ConfigReader
    ) -> None:
        """Test the _yaml_secrets_loader method with a non-ScalarNode."""
        loader = SafeLoader("")
        node = SequenceNode(tag="tag:yaml.org,2002:seq", value=[])
        with pytest.raises(TypeError, match="Expected a ScalarNode"):
            configreader_secfile_sectags._yaml_secrets_loader(loader, node)
