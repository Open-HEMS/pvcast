"""Test all configured weather platforms that inherit from WeatherAPI class."""
from __future__ import annotations

import datetime as dt
from typing import Any, Generator
from urllib.parse import urljoin

# import pandas as pd
import polars as pl
import pytest
import responses
from pvlib.location import Location

from pvcast.weather import API_FACTORY
from pvcast.weather.homeassistant import WeatherAPIHomeassistant
from pvcast.weather.weather import WeatherAPI

from ...const import HASS_TEST_TOKEN, HASS_TEST_URL


class TestWeatherPlatform:
    """Test a weather platform that inherits from WeatherAPI class."""

    weatherapis = API_FACTORY.get_weather_api_list_str()
    valid_temp_units = ["°C", "°F", "C", "F"]
    valid_speed_units = ["m/s", "km/h", "mi/h", "ft/s", "kn"]

    @pytest.fixture
    def time_aliases(
        self, pd_time_aliases: dict[str, list[str]]
    ) -> dict[str, list[str]]:
        return pd_time_aliases

    @pytest.fixture
    def homeassistant_api_setup(
        self, location: Location, ha_weather_data: dict[str, Any]
    ) -> Generator[WeatherAPIHomeassistant, None, None]:
        """Setup the Home Assistant API."""
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                urljoin(HASS_TEST_URL, f"/api/states/{ha_weather_data['entity_id']}"),
                json=ha_weather_data,
                status=200,
            )
            api = WeatherAPIHomeassistant(
                entity_id=ha_weather_data["entity_id"],
                url=HASS_TEST_URL,
                token=HASS_TEST_TOKEN,
                location=location,
            )
            yield api

    @pytest.fixture
    def clearoutside_api_setup(
        self, location: Location, clearoutside_html_page: str
    ) -> Generator[WeatherAPI, None, None]:
        """Setup the Clear Outside API."""
        lat = str(round(location.latitude, 2))
        lon = str(round(location.longitude, 2))
        alt = str(round(location.altitude, 2))

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                urljoin("https://clearoutside.com/forecast/", f"{lat}/{lon}/{alt}"),
                body=clearoutside_html_page,
                status=200,
            )
            api = API_FACTORY.get_weather_api("clearoutside", location=location)
            yield api

    @pytest.fixture(params=weatherapis)
    def weatherapi(
        self, request: pytest.FixtureRequest, location: Location
    ) -> WeatherAPI:
        """Fixture that creates a weather API interface."""
        fixt_val = request.getfixturevalue(f"{request.param}_api_setup")
        if isinstance(fixt_val, WeatherAPI):
            return fixt_val
        else:
            raise ValueError(f"Fixture {request.param}_api_setup not found.")

    @pytest.fixture(params=[1, 2, 5, 10])
    def max_forecast_day(self, request: pytest.FixtureRequest) -> dt.timedelta:
        return dt.timedelta(days=request.param)

    def convert_to_df(self, weather: dict[str, Any]) -> pl.DataFrame:
        """Convert the weather data to a pl.DataFrame."""
        weather_df: pl.DataFrame = pl.DataFrame(weather)
        return weather_df

    def test_weather_get_weather(self, weatherapi: WeatherAPI) -> None:
        """Test the get_weather function."""
        weather = weatherapi.get_weather()
        assert isinstance(weather, dict)
        weather = self.convert_to_df(weather)
        assert isinstance(weather, pl.DataFrame)
        # assert no value is NaN
        sum_nan = weather.null_count().sum_horizontal()
        assert sum_nan.item() == 0
        assert weather.shape[0] >= 24

    @pytest.mark.parametrize("freq", ["1H", "30Min", "15Min"])
    def test_weather_get_weather_freq(
        self, weatherapi: WeatherAPI, freq: str, time_aliases: dict[str, list[str]]
    ) -> None:
        """Test the get_weather function with a number of higher data frequencies."""
        weather = weatherapi.get_weather()
        assert isinstance(weather, dict)
        weather = self.convert_to_df(weather)
        assert isinstance(weather, pl.DataFrame)
        assert pl.infer_freq(weather.index) in time_aliases[freq]
        assert not weather.isna().values.any()
        assert weather.shape[0] >= 24

    def test_weather_get_weather_max_days(
        self,
        weatherapi: WeatherAPI,
        max_forecast_day: dt.timedelta,
        time_aliases: dict[str, list[str]],
    ) -> None:
        """Test the get_weather function with a number of higher data frequencies."""
        freq = "1H"
        weatherapi.max_forecast_days = max_forecast_day
        weather = weatherapi.get_weather()
        assert isinstance(weather, dict)
        weather = self.convert_to_df(weather)
        assert isinstance(weather, pl.DataFrame)
        assert pl.infer_freq(weather.index) in time_aliases[freq]
        assert not weather.isna().values.any()
        assert weather.shape[0] >= 24
        assert weather.shape[0] <= max_forecast_day / dt.timedelta(freq)

    def test_weather_data_cache(self, weatherapi: WeatherAPI) -> None:
        """Test the get_weather function."""
        # get first weather data object
        weather1 = weatherapi.get_weather()
        assert isinstance(weather1, dict)
        weather1 = self.convert_to_df(weather1)
        assert isinstance(weather1, pl.DataFrame)
        last_update1 = weatherapi._last_update

        # get second weather data object, should see that it is cached data
        weather2 = weatherapi.get_weather()
        assert isinstance(weather2, dict)
        weather2 = self.convert_to_df(weather2)
        assert isinstance(weather2, pl.DataFrame)
        last_update2 = weatherapi._last_update
        assert last_update1 == last_update2

    def test_weather_data_live(self, weatherapi: WeatherAPI) -> None:
        """Test the get_weather function."""

        # get first weather data object
        weather1 = weatherapi.get_weather()
        assert isinstance(weather1, dict)
        weather1 = self.convert_to_df(weather1)
        assert isinstance(weather1, pl.DataFrame)
        last_update1 = weatherapi._last_update

        # get second weather data object, should see that it is live data
        weather2 = weatherapi.get_weather(live=True)
        assert isinstance(weather2, dict)
        weather2 = self.convert_to_df(weather2)
        assert isinstance(weather2, pl.DataFrame)
        last_update2 = weatherapi._last_update
        assert last_update1 != last_update2
