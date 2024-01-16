"""Test all configured weather platforms that inherit from WeatherAPI class."""
from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Generator
from urllib.parse import urljoin

import polars as pl
import pytest
import responses
from pvlib.location import Location

from pvcast.weather import API_FACTORY
from pvcast.weather.homeassistant import WeatherAPIHomeassistant
from tests.const import HASS_TEST_TOKEN, HASS_TEST_URL, HASS_WEATHER_ENTITY_ID

from .test_weather import CommonWeatherTests

if TYPE_CHECKING:
    import typing

    from pvcast.weather.weather import WeatherAPI
    from tests.conftest import Location


class WeatherPlatform(CommonWeatherTests):
    """Test a weather platform that inherits from WeatherAPI class."""

    valid_temp_units: typing.ClassVar[list[str]] = ["°C", "°F", "C", "F"]
    valid_speed_units: typing.ClassVar[list[str]] = [
        "m/s",
        "km/h",
        "mi/h",
        "ft/s",
        "kn",
    ]

    @pytest.fixture(params=[1, 2, 5, 10])
    def max_forecast_day(self, request: pytest.FixtureRequest) -> dt.timedelta:
        """Fixture that creates a maximum number of days to forecast."""
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
        assert isinstance(weather, pl.DataFrame)
        assert weather.null_count().sum_horizontal().item() == 0
        assert weather.shape[0] >= 24
        assert weather.shape[0] <= max_forecast_day / dt.timedelta(hours=1)


class TestHomeAssistantWeather(WeatherPlatform):
    """Set up the Home Assistant API."""

    @pytest.fixture
    def homeassistant_api_setup(self, location: Location) -> WeatherAPIHomeassistant:
        """Set up the Home Assistant API."""
        return WeatherAPIHomeassistant(
            location=location,
            url=HASS_TEST_URL,
            token=HASS_TEST_TOKEN,
            entity_id=HASS_WEATHER_ENTITY_ID,
        )

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
        """Set up the Clear Outside API."""
        lat = str(round(location.latitude, 2))
        lon = str(round(location.longitude, 2))

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                urljoin("https://clearoutside.com/forecast/", f"{lat}/{lon}"),
                body=clearoutside_html_page,
                status=200,
            )
            api = API_FACTORY.get_weather_api("clearoutside", location=location)
            yield api

    @pytest.fixture
    def weather_api(self, clearoutside_api_setup: WeatherAPI) -> WeatherAPI:
        """Return the weather api."""
        return clearoutside_api_setup
