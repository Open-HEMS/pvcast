"""Test all configured weather platforms that inherit from WeatherAPI class."""
from __future__ import annotations

from typing import Generator
from urllib.parse import urljoin

import pytest
import responses
from pvlib.location import Location

from pvcast.weather import API_FACTORY
from pvcast.weather.homeassistant import WeatherAPIHomeassistant
from pvcast.weather.weather import WeatherAPI

from ...const import HASS_TEST_TOKEN, HASS_TEST_URL, HASS_WEATHER_ENTITY_ID


class TestWeatherPlatform:
    """Test a weather platform that inherits from WeatherAPI class."""

    weatherapis = API_FACTORY.get_weather_api_list_str()
    valid_temp_units = ["°C", "°F", "C", "F"]
    valid_speed_units = ["m/s", "km/h", "mi/h", "ft/s", "kn"]

    @pytest.fixture
    def homeassistant_api_setup(
        self, location: Location
    ) -> Generator[WeatherAPIHomeassistant, None, None]:
        """Setup the Home Assistant API."""
        api = WeatherAPIHomeassistant(
            location=location,
            url=HASS_TEST_URL,
            token=HASS_TEST_TOKEN,
            entity_id=HASS_WEATHER_ENTITY_ID,
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

    def test_get_weather(self, homeassistant_api_setup: WeatherAPI) -> None:
        """Test the get_weather function."""
        # # Check if the fixture used is homeassistant_api_setup
        # if isinstance(weatherapi, WeatherAPIHomeassistant):
        #     pytest.skip("Test not applicable to Home Assistant API")
        weather = homeassistant_api_setup.get_weather()
        assert isinstance(weather, dict)
