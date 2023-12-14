"""Weather API class that retrieves weather data from Home Assistant"""

from __future__ import annotations

import logging
from dataclasses import InitVar, dataclass, field

import polars as pl

from ..homeassistant.homeassistantapi import HomeAssistantAPI
from .weather import WeatherAPI

_LOGGER = logging.getLogger(__name__)


@dataclass
class WeatherAPIHomeassistant(WeatherAPI):
    """Weather API class that retrieves weather data from Home Assistant entity."""

    entity_id: InitVar[str] = field(default="")
    token: InitVar[str] = field(default="")
    sourcetype: str = field(default="homeassistant")
    _hass_api: HomeAssistantAPI = field(init=False)

    def __post_init__(
        self: WeatherAPIHomeassistant, entity_id: str, token: str
    ) -> None:
        """Initialize the Home Assistant API interface."""
        self._hass_api = HomeAssistantAPI(self.url, token, entity_id)

    def retrieve_new_data(self) -> pl.DataFrame:
        """
        Retrieve new weather data from the API.

        :return: Response from the API
        """
        weather_df: pl.DataFrame = pl.from_dicts(self._hass_api.forecast)
