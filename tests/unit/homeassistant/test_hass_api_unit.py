"""Test Home Assistant API class."""
from __future__ import annotations

from typing import Union

import pytest

from pvcast.homeassistant.homeassistantapi import HomeAssistantAPI

from ...const import HASS_TEST_TOKEN, HASS_TEST_URL, HASS_WEATHER_ENTITY_ID


@pytest.mark.integration
class TestHomeAssistantAPI:
    """Test the Home Assistant API class."""

    @pytest.fixture
    def homeassistant_api(self) -> HomeAssistantAPI:
        """Return a Home Assistant API instance."""
        return HomeAssistantAPI(
            host=HASS_TEST_URL,
            entity_id=HASS_WEATHER_ENTITY_ID,
            token=HASS_TEST_TOKEN,
        )

    def test_init_correct(self, homeassistant_api: HomeAssistantAPI) -> None:
        """Test the Home Assistant API initialization."""
        assert homeassistant_api.url == f"ws://{HASS_TEST_URL}/api/websocket"
        assert homeassistant_api._auth_headers == {
            "type": "auth",
            "access_token": HASS_TEST_TOKEN,
        }
        assert homeassistant_api._data_headers == {
            "id": -1,
            "type": "weather/subscribe_forecast",
            "entity_id": HASS_WEATHER_ENTITY_ID,
            "forecast_type": "hourly",
        }

    @pytest.mark.parametrize(
        ("entity_id", "expected", "match"),
        [
            ("weather.forecast_thuis", None, None),
            ("weather.forecast.thuis", ValueError, "Invalid entity_id"),
            ("weather", ValueError, "Invalid entity_id"),
            ("invalid_entity_id", ValueError, "Invalid entity_id"),
            ("sensor.forecast_thuis", ValueError, "Only weather entities"),
        ],
    )
    def test_init_wrong_entity_id(
        self, entity_id: str, expected: Union[None, Exception], match: Union[None, str]
    ) -> None:
        """Test the Home Assistant API initialization with wrong entity_id."""
        if expected is None:
            HomeAssistantAPI(
                host=HASS_TEST_URL,
                entity_id=entity_id,
                token=HASS_TEST_TOKEN,
            )
        else:
            with pytest.raises(expected, match=match):
                HomeAssistantAPI(
                    host=HASS_TEST_URL,
                    entity_id=entity_id,
                    token=HASS_TEST_TOKEN,
                )

    def test_online(self, homeassistant_api: HomeAssistantAPI) -> None:
        """Test the online property."""
        assert homeassistant_api.online

    def test_data_headers(self, homeassistant_api: HomeAssistantAPI) -> None:
        """Test the data_headers property."""
        assert set(homeassistant_api.data_headers.keys()) == {
            "id",
            "type",
            "entity_id",
            "forecast_type",
        }
        assert isinstance(homeassistant_api.data_headers["id"], int)
        assert homeassistant_api.data_headers["id"] > 0
        assert homeassistant_api.data_headers["type"] == "weather/subscribe_forecast"
        assert homeassistant_api.data_headers["entity_id"] == self.weather_entity_id
        assert homeassistant_api.data_headers["forecast_type"] == "hourly"

    def test_get_forecast(self, homeassistant_api: HomeAssistantAPI) -> None:
        """Test the get_forecast method."""
        forecast = homeassistant_api.forecast
        print(f"Forecast: {forecast}")
        assert forecast is not None
