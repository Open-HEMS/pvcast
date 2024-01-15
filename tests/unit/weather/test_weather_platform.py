"""Test all configured weather platforms that inherit from WeatherAPI class."""
from __future__ import annotations

import datetime as dt
from typing import Generator
from urllib.parse import urljoin

import polars as pl
import pytest
import responses
from pvlib.location import Location

from pvcast.weather import API_FACTORY
from pvcast.weather.homeassistant import WeatherAPIHomeassistant
from pvcast.weather.weather import WeatherAPI

from ...const import HASS_TEST_TOKEN, HASS_TEST_URL, HASS_WEATHER_ENTITY_ID
from .test_weather import CommonWeatherTests


class WeatherPlatform(CommonWeatherTests):
    """Test a weather platform that inherits from WeatherAPI class."""

    weather_apis = API_FACTORY.get_weather_api_list_str()
    valid_temp_units = ["°C", "°F", "C", "F"]
    valid_speed_units = ["m/s", "km/h", "mi/h", "ft/s", "kn"]

    @pytest.fixture(params=[1, 2, 5, 10])
    def max_forecast_day(self, request: pytest.FixtureRequest) -> dt.timedelta:
        return dt.timedelta(days=request.param)

    def test_get_weather(self, weather_api: WeatherAPI) -> None:
        """Test the get_weather function."""
        data = weather_api.get_weather()["data"]
        weather = pl.from_dicts(data)
        assert isinstance(weather, pl.DataFrame)
        assert weather.null_count().sum_horizontal().item() == 0
        assert weather.shape[0] >= 24

    def test_weather_get_weather_max_days(
        self,
        weather_api: WeatherAPI,
        max_forecast_day: dt.timedelta,
    ) -> None:
        """Test the get_weather function with a maximum number of days to forecast."""
        weather_api.max_forecast_days = max_forecast_day
        data = weather_api.get_weather()["data"]
        weather = pl.from_dicts(data)
        print(f"[n_days={max_forecast_day}]:\n{weather}")
        assert isinstance(weather, pl.DataFrame)
        assert weather.null_count().sum_horizontal().item() == 0
        assert weather.shape[0] >= 24
        assert weather.shape[0] <= max_forecast_day / dt.timedelta(hours=1)


class TestHomeAssistantWeather(WeatherPlatform):
    """Test a weather platform that inherits from WeatherAPI class."""

    @pytest.fixture
    def homeassistant_api_setup(self, location: Location) -> WeatherAPIHomeassistant:
        """Setup the Home Assistant API."""
        api = WeatherAPIHomeassistant(
            location=location,
            url=HASS_TEST_URL,
            token=HASS_TEST_TOKEN,
            entity_id=HASS_WEATHER_ENTITY_ID,
        )
        return api

    @pytest.fixture
    def weather_api(
        self, homeassistant_api_setup: WeatherAPIHomeassistant
    ) -> WeatherAPI:
        """Return the weather api."""
        return homeassistant_api_setup


class TestClearOutsideWeather(WeatherPlatform):
    """Test a weather platform that inherits from WeatherAPI class."""

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

    @pytest.fixture
    def weather_api(self, clearoutside_api_setup: WeatherAPI) -> WeatherAPI:
        """Return the weather api."""
        return clearoutside_api_setup
