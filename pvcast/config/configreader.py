"""Reads PV plant configuration from a YAML file."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pytz
import yaml
from pytz import UnknownTimeZoneError
from voluptuous import Coerce, Optional, Required, Schema

_LOGGER = logging.getLogger(__name__)


@dataclass
class ConfigReader:
    """Reads PV plant configuration from a YAML file."""

    _secrets: dict = field(init=False, repr=False)
    _config: dict = field(init=False, repr=False)
    config_file_path: Path = field(repr=True)
    secrets_file_path: Path | None = field(repr=True, default=None)

    def __post_init__(self) -> None:
        """Initialize the class."""
        if not self.config_file_path.exists():
            raise FileNotFoundError(f"Configuration file {self.config_file_path} not found.")

        # load secrets file and add loader for secrets
        if self.secrets_file_path is not None:
            self._load_secrets_file()
            yaml.add_constructor("!secret", self._yaml_secrets_loader, Loader=yaml.SafeLoader)
            _LOGGER.info("Loaded secrets file %s", self.secrets_file_path)

        # load the main configuration file
        with self.config_file_path.open(encoding="utf-8") as config_file:
            try:
                config = yaml.safe_load(config_file)
            except yaml.YAMLError as exc:
                _LOGGER.error(
                    "Error parsing configuration file %s. Did you include secrets.yaml?", self.config_file_path
                )
                raise yaml.YAMLError(f"Error parsing configuration file {self.config_file_path}") from exc
            self._validate_config(config)

        # check if the timezone is valid
        try:
            config["general"]["location"]["timezone"] = pytz.timezone(config["general"]["location"]["timezone"])
        except UnknownTimeZoneError as exc:
            raise UnknownTimeZoneError(f"Unknown timezone {config['general']['location']['timezone']}") from exc

        self._config = config

    def _yaml_secrets_loader(self, loader: yaml.SafeLoader, node: yaml.Node) -> str:
        """Load secrets from the secrets file.

        :param loader: The YAML loader.
        :param node: The YAML node.
        :return: The secret.
        """
        value = loader.construct_scalar(node)
        secret = self._secrets.get(value)
        if secret is None:
            raise ValueError(f"Secret {value} not found in {self.secrets_file_path}!")
        return secret

    def _load_secrets_file(self) -> None:
        """Load secrets from a file.

        :param secrets_file_path: The path to the secrets file.
        """
        if self.secrets_file_path is None:
            self._secrets = {}
            _LOGGER.warning("No secrets file path given. Continuing without secrets!")
            return
        if not self.secrets_file_path.exists():
            raise FileNotFoundError(f"Secrets file {self.secrets_file_path} not found.")

        with self.secrets_file_path.open(encoding="utf-8") as secrets_file:
            self._secrets = yaml.safe_load(secrets_file)

    @property
    def config(self) -> dict:
        """Parse the YAML configuration and return it as a dictionary.

        :return: The configuration as a dictionary.
        """
        return self._config

    @property
    def _config_schema(self) -> dict:
        """Get the configuration schema as a dictionary.

        :return: Config schema dictionary.
        """
        return Schema(
            {
                Required("general"): {
                    "weather_sources": [
                        {
                            Required("type"): str,
                            Required("source"): str,
                            Optional("api_key"): str,
                        }
                    ],
                    "location": {
                        Required("latitude"): float,
                        Required("longitude"): float,
                        Required("altitude"): Coerce(float),
                        Required("timezone"): str,
                    },
                    Required("long_lived_token"): str,
                },
                Required("plant"): [
                    {
                        Required("name"): str,
                        Required("inverter"): str,
                        Required("microinverter"): bool,
                        Required("arrays"): [
                            {
                                Required("name"): str,
                                Required("tilt"): Coerce(float),
                                Required("azimuth"): Coerce(float),
                                Required("modules_per_string"): int,
                                Required("strings"): int,
                                Required("module"): str,
                            }
                        ],
                    }
                ],
            }
        )

    def _validate_config(self, config: dict) -> None:
        """Validate the YAML configuration.

        :param config: The configuration to validate.
        """
        Schema(self._config_schema)(config)
