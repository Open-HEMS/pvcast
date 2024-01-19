"""Weather API class that retrieves weather data from Home Assistant."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import InitVar, dataclass, field

import polars as pl

from pvcast.homeassistant.homeassistantapi import HomeAssistantAPI

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
        """Retrieve new weather data from the API.

        :return: Response from the API
        """
        weather_df: pl.DataFrame = pl.from_dicts(self._hass_api.forecast)
        weather_df = weather_df.rename({"cloud_coverage": "cloud_cover"})

        # select relevant columns
        weather_df = weather_df.select(
            ["datetime", "temperature", "humidity", "wind_speed", "cloud_cover"]
        )

        # interpolate NaN values
        weather_df = weather_df.interpolate()
        weather_df = weather_df.drop_nulls()

        # convert datetime column to datetime
        weather_df = weather_df.with_columns(pl.col("datetime").str.to_datetime())

        # check that timezone is in UTC, if not, convert it
        time_zone = weather_df["datetime"].dtype.time_zone  # type: ignore[attr-defined]
        if time_zone != str(dt.timezone.utc):
            _LOGGER.warning("HA weather data timezone is not UTC but: %s", time_zone)
            weather_df = weather_df.with_columns(
                pl.col("datetime").cast(pl.Datetime(time_zone=dt.timezone.utc))
            )
        return weather_df
