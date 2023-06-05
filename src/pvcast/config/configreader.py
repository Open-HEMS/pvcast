"""Reads PV plant configuration from a YAML file."""

from pathlib import Path

import yaml


class ConfigReader:
    """Reads PV plant configuration from a YAML file."""

    def __init__(self, config_file_path: Path):
        """Initialize a ConfigReader.

        :param config_file_path: The path to the YAML configuration file.
        """
        self._config_file_path: Path = config_file_path

    @property
    def config_file_path(self) -> Path:
        """Get the path to the YAML configuration file.

        :return: The path to the YAML configuration file.
        """
        return self._config_file_path

    @property
    def config(self) -> dict:
        """Get the configuration as a dictionary.

        :return: The configuration as a dictionary.
        """
        if not self._config_file_path.exists():
            raise FileNotFoundError(f"Configuration file {self._config_file_path} not found.")
        with self._config_file_path.open() as config_file:
            config = yaml.safe_load(config_file)
        return config
