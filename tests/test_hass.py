"""Test Home Assistant API class."""
from __future__ import annotations

import pytest
from const import HASS_TEST_TOKEN, HASS_TEST_URL

from pvcast.hass.hass import HassAPI


class TestHassAPI:
    """Test the Home Assistant API class."""

    @pytest.fixture()
    def hass_api(self):
        """Fixture for the Home Assistant API."""
        return HassAPI(hass_url=HASS_TEST_URL, token=HASS_TEST_TOKEN)

    def test_hass_api_url(self, hass_api: HassAPI):
        """Test the url property."""
        assert hass_api.url == HASS_TEST_URL + "/api/"

    def test_hass_api_online(self, hass_api: HassAPI):
        """Test the online property."""
        assert hass_api.online

    def test_hass_api_headers(self, hass_api: HassAPI):
        """Test the headers property."""
        assert hass_api.headers == {
            "Authorization": "Bearer " + HASS_TEST_TOKEN,
            "Content-Type": "application/json",
        }

    def test_hass_api_get_entity_state(self, hass_api: HassAPI):
        """Test the get_entity_state method."""
        entity_data = hass_api.get_entity_state("weather.forecast_thuis_hourly")
        assert entity_data["entity_id"] == "weather.forecast_thuis_hourly"
        assert len(entity_data["attributes"]["forecast"]) % 24 == 0
        assert all(
            [
                prop in entity_data["attributes"]["forecast"][0].keys()
                for prop in [
                    "condition",
                    "datetime",
                    "wind_bearing",
                    "cloud_coverage",
                    "temperature",
                    "wind_speed",
                    "precipitation",
                    "humidity",
                ]
            ]
        )
