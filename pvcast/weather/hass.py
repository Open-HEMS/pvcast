"""Weather API class that scrapes the data from Clear Outside."""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field

import pandas as pd
from requests import Response

from ..hass.hassapi import HassAPI
from ..weather.weather import WeatherAPI

_LOGGER = logging.getLogger(__name__)


@dataclass
class WeatherAPIHASS(WeatherAPI):
    """Weather API class that retrieves weather data from Home Assistant entity."""

    sourcetype: str = field(default="homeassistant")
    entity_id: str = field(default=None)
    url: str = field(default=None)
    token: str = field(default=None)
    _hass_api: HassAPI = field(init=False)

    def __post_init__(self):
        if not self.entity_id:
            raise ValueError("Entity ID not set.")
        if not self.token:
            raise ValueError("Token not set.")
        self._hass_api = HassAPI(token=self.token, hass_url=self.url)

    def _do_request(self) -> Response:
        """
        Get the weather data from the Home Assistant API.
        Override the _do_request method from the WeatherAPI class.

        :return: Response from Home Assistant API.
        """
        return self._hass_api.get_entity_state(self.entity_id)

    def _process_data(self) -> pd.DataFrame:
        """Process weather data from the Home Assistant API.

        This function takes no arguments, but response.content must be retrieved from self._raw_data.

        :return: Processed weather data.
        """
        # raw response data from request
        response = self._raw_data.json()
        weather_df = pd.DataFrame(response["attributes"]["forecast"])
        weather_df["datetime"] = pd.to_datetime(weather_df["datetime"])
        weather_df.set_index("datetime", inplace=True)

        # convert units if needed
        units = {
            "temperature": "°C",
            "wind_speed": "m/s",
        }

        for key, unit in units.items():
            weather_df[key] = self.convert_unit(
                weather_df[key],
                from_unit=response["attributes"][f"{key}_unit"],
                to_unit=unit,
            )

        # check timezone is UTC
        if not weather_df.index.tz == datetime.timezone.utc:
            raise ValueError(f"Timezone is not UTC: {weather_df.index.tz}")

        # select columns
        weather_df = weather_df[
            ["temperature", "humidity", "cloud_coverage", "wind_speed"]
        ]

        # add data frequency
        weather_df.index = self._add_freq(weather_df.index)
        return weather_df
