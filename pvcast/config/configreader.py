"""Reads PV plant configuration from a YAML file."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytz
import yaml
from pytz import UnknownTimeZoneError
from voluptuous import Any, Coerce, Required, Schema, Url

if TYPE_CHECKING:
    from pathlib import Path

_LOGGER = logging.getLogger(__name__)


class Loader(yaml.SafeLoader):
    """Custom YAML loader."""


@dataclass
class ConfigReader:
    """Reads PV plant configuration from a YAML file."""

    _secrets: dict[str, Any] = field(init=False, repr=False)
    _config: dict[str, Any] = field(init=False, repr=False)
    config_file_path: Path = field(repr=True)
    secrets_file_path: Path | None = field(repr=True, default=None)

    def __post_init__(self) -> None:
        """Initialize the class."""
        if not self.config_file_path.exists():
            msg = f"Configuration file {self.config_file_path} not found."
            raise FileNotFoundError(msg)

        # load the main configuration file
        with self.config_file_path.open(encoding="utf-8") as config_file:
            # load secrets file and add loader for secrets
            try:
                if self.secrets_file_path is not None:
                    self._load_secrets_file()
                    Loader.add_constructor("!secret", self._yaml_secrets_loader)
                    config = next(yaml.load_all(config_file, Loader=Loader))
                else:
                    config = yaml.safe_load(config_file)
                    _LOGGER.info("No secrets file loaded")

                # validate the configuration
                Schema(self._config_schema)(config)
            except yaml.YAMLError as exc:
                _LOGGER.exception(
                    "Error parsing configuration file %s. Did you include secrets.yaml?",
                    self.config_file_path,
                )
                msg = f"Error parsing configuration file {self.config_file_path}"
                raise yaml.YAMLError(msg) from exc

        # check if the timezone is valid
        try:
            config["general"]["location"]["timezone"] = pytz.timezone(
                config["general"]["location"]["timezone"]
            )
        except UnknownTimeZoneError as exc:
            msg = f"Unknown timezone {config['general']['location']['timezone']}"
            raise UnknownTimeZoneError(msg) from exc

        self._config = config

    def _yaml_secrets_loader(self, loader: yaml.SafeLoader, node: yaml.Node) -> Any:
        """Load secrets from the secrets file.

        :param loader: The YAML loader.
        :param node: The YAML node.
        :return: The secret.
        """
        if isinstance(node, yaml.ScalarNode):
            key = str(loader.construct_scalar(node))
        else:
            msg = "Expected a ScalarNode"
            raise TypeError(msg)

        secret = self._secrets.get(key)
        if secret is None:
            _LOGGER.error("Secret not found in %s!", self.secrets_file_path)
            msg = f"Secret not found in {self.secrets_file_path}!"
            raise yaml.YAMLError(msg)
        return secret

    def _load_secrets_file(self) -> None:
        """Load secrets from a file.

        :param secrets_file_path: The path to the secrets file.
        """
        if self.secrets_file_path is None:
            msg = "Secrets file path is not set."
            raise ValueError(msg)

        if not self.secrets_file_path.exists():
            msg = f"Secrets file {self.secrets_file_path} not found."
            raise FileNotFoundError(msg)

        with self.secrets_file_path.open(encoding="utf-8") as secrets_file:
            self._secrets = yaml.full_load(secrets_file)

    @property
    def config(self) -> dict[str, Any]:
        """Parse the YAML configuration and return it as a dictionary.

        :return: The configuration as a dictionary.
        """
        return self._config

    @property
    def _config_schema(self) -> Schema:
        """Get the configuration schema as a Schema object.

        :return: Config schema.
        """
        homessistant = Schema(
            {
                Required("type"): "homeassistant",
                Required("entity_id"): str,
                Required("url"): Url,
                Required("token"): str,
                Required("name"): str,
            }
        )
        clearoutside = Schema({Required("type"): "clearoutside", Required("name"): str})
        return Schema(
            {
                Required("general"): {
                    Required("weather"): {
                        Required("sources"): [Any(homessistant, clearoutside)],
                        Required("max_forecast_days"): Coerce(int),
                    },
                    Required("location"): {
                        Required("latitude"): float,
                        Required("longitude"): float,
                        Required("altitude"): Coerce(float),
                        Required("timezone"): str,
                    },
                },
                Required("plant"): [
                    {
                        Required("name"): str,
                        Required("inverter"): str,
                        Required("microinverter"): Coerce(bool),
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
