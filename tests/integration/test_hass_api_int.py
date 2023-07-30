"""Integration test for Home Assistant API class."""
from __future__ import annotations

import pytest
import requests
from const import HASS_TEST_TOKEN, HASS_TEST_URL

from pvcast.hass.hassapi import HassAPI


class TestHassAPI:
    """Test the Home Assistant API class."""

    @pytest.fixture(params=["weather.forecast_thuis_hourly"])
    def weather_entity_id(self, request):
        """Fixture for the weather entity id."""
        return request.param

    @pytest.fixture()
    def hass_api(self):
        """Fixture for the Home Assistant API."""
        return HassAPI(hass_url=HASS_TEST_URL, token=HASS_TEST_TOKEN)

    def test_hass_api_get_entity_state(self, hass_api: HassAPI, weather_entity_id):
        """Test the get_entity_state method."""
        entity_data: requests.Response = hass_api.get_entity_state(weather_entity_id)
        assert entity_data.ok
        assert entity_data.status_code == 200
        assert entity_data.headers["Content-Type"] == "application/json"
        assert entity_data.headers["Content-Encoding"] == "deflate"
        entity_data = entity_data.json()
        assert entity_data["entity_id"] == weather_entity_id
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
