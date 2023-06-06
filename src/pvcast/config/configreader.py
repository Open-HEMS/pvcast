"""Reads PV plant configuration from a YAML file."""

import logging
from pathlib import Path
from dataclasses import dataclass, field

import pytz
from voluptuous import Required, Schema, Optional, Coerce
import yaml


_LOGGER = logging.getLogger(__name__)


@dataclass()
class ConfigReader:
    """Reads PV plant configuration from a YAML file."""

    _secrets: dict = field(init=False, repr=False)
    config_file_path: Path = field(repr=True)
    secrets_file_path: Path = field(repr=True, default=None)

    def _yaml_secrets_loader(self, loader: yaml.SafeLoader, node: yaml.Node) -> str:
        """Load secrets from the secrets file.

        :param loader: The YAML loader.
        :param node: The YAML node.
        :return: The secret.
        """
        value = loader.construct_scalar(node)
        secret = self._secrets.get(value)
        if secret is None:
            raise ValueError(f"Secret {value} not found in secrets.yaml")
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
        if not self.config_file_path.exists():
            raise FileNotFoundError(f"Configuration file {self.config_file_path} not found.")

        # load secrets file and add loader for secrets
        try:
            self._load_secrets_file()
        except FileNotFoundError:
            _LOGGER.warning("No secrets file found at given path. Continuing without secrets!")
            self._secrets = {}
        yaml.add_constructor("!secret", self._yaml_secrets_loader, Loader=yaml.SafeLoader)

        # load the main configuration file
        with self.config_file_path.open(encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file)
            self._validate_config(config)

        # Convert time zone string to pytz.timezone object
        config["general"]["timezone"] = pytz.timezone(config["general"]["timezone"])

        return config

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
                    },
                    Required("timezone"): str,
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
