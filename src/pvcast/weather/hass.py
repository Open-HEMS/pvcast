"""Weather API class that scrapes the data from Clear Outside."""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field

from pandas import DataFrame, infer_freq, to_datetime
from requests import Response

from ..hass.hassapi import HassAPI
from ..weather.weather import WeatherAPI

_LOGGER = logging.getLogger(__name__)


@dataclass
class WeatherAPIHASS(WeatherAPI):
    """Weather API class that retrieves weather data from Home Assistant entity."""

    include_current: bool = False
    entity_id: str = field(default=None)
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

    def _process_data(self) -> DataFrame:
        """Process weather data scraped from the clear outside website.

        Credits to https://github.com/davidusb-geek/emhass for the parsing code.

        This function takes no arguments, but response.content must be retrieved from self._raw_data.
        """
        # raw response data from request
        response = self._raw_data.json()

        # check if entity_id is correct
        if not response["entity_id"] == self.entity_id:
            raise ValueError(f"Entity ID is not correct: {response['entity_id']}")

        weather_df = DataFrame(response["attributes"]["forecast"])
        weather_df["datetime"] = to_datetime(weather_df["datetime"])
        weather_df.set_index("datetime", inplace=True)

        # convert F to C if needed
        if response["attributes"]["temperature_unit"] == "°F":
            weather_df["temperature"] = (weather_df["temperature"] - 32) * 5 / 9
        elif response["attributes"]["temperature_unit"] != "°C":
            raise ValueError(f"Temperature unit is not °C or °F: {response['attributes']['temperature_unit']}")

        # convert wind_speed_unit from [km/h, mi/h, ft/s, kn] to  m/s if needed
        wind_speed_unit = response["attributes"]["wind_speed_unit"]
        conv_dict = {"km/h": 0.277777778, "mi/h": 0.44704, "ft/s": 0.3048, "kn": 0.51444}
        if wind_speed_unit != "m/s":
            weather_df["wind_speed"] = weather_df["wind_speed"] * conv_dict[wind_speed_unit]

        # check timezone is UTC
        if not weather_df.index.tz == datetime.timezone.utc:
            raise ValueError(f"Timezone is not UTC: {weather_df.index.tz}")

        # select columns
        weather_df = weather_df[["temperature", "humidity", "cloud_coverage", "wind_speed"]]
        return weather_df
