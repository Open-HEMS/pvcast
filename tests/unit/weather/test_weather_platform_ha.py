"""Tests specific to the homeassistantweather platform."""
from __future__ import annotations

from typing import Any, Generator
from urllib.parse import urljoin

import pandas as pd
import pytest
import requests
import responses
from pvlib.location import Location

from pvcast.weather.homeassistant import WeatherAPIHomeassistant

from ...const import HASS_TEST_TOKEN, HASS_TEST_URL


class TestWeatherPlatformHASS:
    """A few extra tests for the homeassistant weather platform specific functionality."""

    hass_url = urljoin(HASS_TEST_URL, "/api/")
    valid_temp_units = ["°C", "°F", "C", "F"]
    valid_speed_units = ["m/s", "km/h", "mi/h", "ft/s", "kn"]
    conv_dict_speed = {
        "km/h": 0.277777778,
        "mi/h": 0.44704,
        "ft/s": 0.3048,
        "kn": 0.51444,
    }
    token = HASS_TEST_TOKEN

    @pytest.fixture(params=valid_temp_units + ["wrong"])
    def temperature_unit(
        self, ha_weather_data: dict[str, Any], request: pytest.FixtureRequest
    ) -> dict[str, Any]:
        """Load the weather test data."""
        ha_weather_data["attributes"]["temperature_unit"] = request.param
        return ha_weather_data

    @pytest.fixture(params=valid_speed_units + ["wrong"])
    def wind_speed_unit(
        self, temperature_unit: dict[str, Any], request: pytest.FixtureRequest
    ) -> dict[str, Any]:
        """Load the weather test data."""
        temperature_unit["attributes"]["wind_speed_unit"] = request.param
        return temperature_unit

    @pytest.fixture
    def weatherapi(self, location: Location) -> WeatherAPIHomeassistant:
        """Fixture that creates a weather API interface."""
        return WeatherAPIHomeassistant(
            entity_id="weather.forecast_thuis_hourly",
            url=HASS_TEST_URL,
            token=HASS_TEST_TOKEN,
            location=location,
        )

    @pytest.fixture
    def mock_ha_api(
        self, wind_speed_unit: dict[str, Any], weatherapi: WeatherAPIHomeassistant
    ) -> Generator[WeatherAPIHomeassistant, None, None]:
        """Mock a HA weather API response and return the weatherapi object."""
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET, HASS_TEST_URL + "/api/", json=wind_speed_unit, status=200
            )
            yield weatherapi

    def test_hass_init_errors(self) -> None:
        """Init WeatherAPIhomeassistantwith wrong parameters."""
        with pytest.raises(ValueError, match="Token not set."):
            WeatherAPIHomeassistant(
                entity_id="weather.forecast_thuis_hourly",
                url=HASS_TEST_URL,
                token=None,
                location=None,
            )
        with pytest.raises(ValueError, match="Entity ID not set."):
            WeatherAPIHomeassistant(
                entity_id=None,
                url=HASS_TEST_URL,
                token=None,
                location=None,
            )

    def test_hass_process_data(self, mock_ha_api: WeatherAPIHomeassistant) -> None:
        """Test the process_data function."""
        resp = requests.get(self.hass_url)
        mock_ha_api._raw_data = resp
        temp_unit = mock_ha_api._raw_data.json()["attributes"]["temperature_unit"]
        wind_unit = mock_ha_api._raw_data.json()["attributes"]["wind_speed_unit"]

        # test the _process_data function
        if (
            temp_unit not in self.valid_temp_units
            or wind_unit not in self.valid_speed_units
        ):
            with pytest.raises(ValueError):
                mock_ha_api._process_data()
        else:
            weather_df = mock_ha_api._process_data()
            assert isinstance(weather_df, pd.DataFrame)
            assert not weather_df.isna().values.any()

    @responses.activate
    def test_hass_data_wrong_timezone(self, ha_weather_data: dict[str, Any]) -> None:
        """Test the process_data function with wrong timezone"""
        forecast = ha_weather_data["attributes"]["forecast"]
        for datadict in forecast:
            datadict["datetime"] = datadict["datetime"].replace("+00:00", "+01:00")
        ha_weather_data["attributes"]["forecast"] = forecast
        responses.add(responses.GET, self.hass_url, json=ha_weather_data, status=200)
        resp = requests.get(self.hass_url)

        # test the _process_data function
        weatherapi = WeatherAPIHomeassistant(
            entity_id="test.entity",
            url=HASS_TEST_URL,
            token=HASS_TEST_TOKEN,
            location=Location(0, 0),
        )
        weatherapi._raw_data = resp

        # see if ValueError is raised for wrong timezone
        with pytest.raises(ValueError, match="Timezone is not UTC:"):
            weatherapi._process_data()
