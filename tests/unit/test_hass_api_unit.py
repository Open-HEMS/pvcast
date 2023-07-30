"""Test Home Assistant API class."""
from __future__ import annotations

from urllib.parse import urljoin

from pvlib.location import Location
import pandas as pd
import pytest
import requests
import responses
from const import HASS_TEST_TOKEN, HASS_TEST_URL

from pvcast.weather.hass import WeatherAPIHASS
from pvcast.hass.hassapi import HassAPI


class TestHassAPI:
    """Test the Home Assistant API class."""

    url = urljoin(HASS_TEST_URL, "api/")
    weather_entity_id = "weather.forecast_thuis_hourly"
    entity_not_found = "not.found"
    entity_url = urljoin(url, f"states/{weather_entity_id}")
    post_response = {
        "entity_id": "sensor.kitchen_temperature",
        "state": "25",
        "attributes": {"unit_of_measurement": "°C"},
        "last_changed": "2023-07-27T10:33:35.834356+00:00",
        "last_updated": "2023-07-27T10:33:35.834356+00:00",
        "context": {
            "id": "01H6BEJFTTT1W8BJ905B2YS3JA",
            "parent_id": None,
            "user_id": "f20d2b011d0f40c182c676dce72bd6a2",
        },
    }

    @pytest.fixture
    def mocked_ha_response(self):
        """See: https://github.com/getsentry/responses#responses-as-a-pytest-fixture"""
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, self.url, json={}, status=200)
            yield rsps

    @pytest.fixture
    def mocked_ha_response_err(self):
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, self.entity_url, json={}, status=500)
            yield rsps

    @pytest.fixture
    def mocked_ha_post(self):
        with responses.RequestsMock() as rsps:
            rsps.add(responses.POST, self.entity_url, json=self.post_response, status=200)
            yield rsps

    @pytest.fixture
    def mocked_ha_post_err(self):
        with responses.RequestsMock() as rsps:
            rsps.add(responses.POST, self.entity_url, json={}, status=500)
            yield rsps

    @pytest.fixture
    def mocked_ha_weather_data(self, ha_weather_data):
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, self.entity_url, json=ha_weather_data, status=200)
            yield rsps

    @pytest.fixture
    def mocked_ha_entity_not_found(self):
        entity_url = urljoin(self.url, f"states/{self.entity_not_found}")
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, entity_url, json={}, status=404)
            yield rsps

    @pytest.fixture
    def hass_api(self):
        """Fixture for the Home Assistant API."""
        return HassAPI(hass_url=HASS_TEST_URL, token=HASS_TEST_TOKEN)

    def test_url(self, hass_api: HassAPI):
        """Test the url property."""
        assert hass_api.url == self.url

    def test_hass_online(self, hass_api: HassAPI, mocked_ha_response):
        """Test the online property."""
        assert hass_api.online

    def test_api_headers(self, hass_api: HassAPI):
        """Test the headers property."""
        assert hass_api.headers == {
            "Authorization": "Bearer " + HASS_TEST_TOKEN,
            "Content-Type": "application/json",
        }

    def test_get_entity_state(self, hass_api: HassAPI, mocked_ha_weather_data):
        """Test the get_entity_state method."""
        entity_data: requests.Response = hass_api.get_entity_state(self.weather_entity_id)
        assert entity_data.ok
        assert entity_data.status_code == 200
        assert entity_data.headers["Content-Type"] == "application/json"
        entity_data = entity_data.json()
        assert entity_data["entity_id"] == self.weather_entity_id
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

    def test_get_entity_state_wrong_entity_id(self, hass_api: HassAPI):
        """Test the get_entity_state method with a wrong entity_id."""
        with pytest.raises(ValueError):
            hass_api.get_entity_state("wrongentity_id")

    def test_get_entity_state_not_found(self, hass_api: HassAPI, mocked_ha_entity_not_found):
        """Test the get_entity_state method when the entity is not found."""
        with pytest.raises(ValueError):
            hass_api.get_entity_state("not.found")

    def test_get_entity_state_connection_error(self, hass_api: HassAPI, mocked_ha_response_err):
        """Test the get_entity_state method when the connection fails."""
        with pytest.raises(requests.ConnectionError):
            hass_api.get_entity_state(self.weather_entity_id)

    def test_post_entity_state(self, hass_api: HassAPI, mocked_ha_post):
        """Test the post_state method."""
        entity_data: requests.Response = hass_api.post_entity_state(
            self.weather_entity_id, {"state": "25", "attributes": {"unit_of_measurement": "°C"}}
        )
        assert entity_data.ok
        assert entity_data.status_code == 200
        assert entity_data.headers["Content-Type"] == "application/json"
        entity_data = entity_data.json()
        assert entity_data["entity_id"] == "sensor.kitchen_temperature"
        assert entity_data["state"] == "25"
        assert entity_data["attributes"]["unit_of_measurement"] == "°C"
        assert "last_changed" in entity_data.keys()
        assert "last_updated" in entity_data.keys()

    def test_post_entity_state_connection_error(self, hass_api: HassAPI, mocked_ha_post_err):
        """Test the post_state method when the connection fails."""
        with pytest.raises(requests.ConnectionError):
            hass_api.post_entity_state(
                self.weather_entity_id, {"state": "25", "attributes": {"unit_of_measurement": "°C"}}
            )
