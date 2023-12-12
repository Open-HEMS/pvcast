"""Home Assistant API interface. Handles the communication with the Home Assistant API."""

from __future__ import annotations

import json
import logging
import random
import typing
from dataclasses import InitVar, dataclass, field
from typing import Dict, Union

from voluptuous import All, Coerce, Range, Required, Schema
from websockets.sync.client import Connection, connect  # type: ignore

_LOGGER = logging.getLogger(__name__)


forecast_item_schema = Schema(
    {
        Required("condition"): str,
        Required("datetime"): str,
        Required("wind_bearing"): Coerce(float),
        Required("cloud_coverage"): Coerce(float),
        Required("temperature"): Coerce(float),
        Required("wind_speed"): Coerce(float),
        Required("precipitation"): Coerce(float),
        Required("humidity"): All(int, Range(min=0, max=100)),
    }
)

event_schema = Schema(
    {
        Required("type"): str,
        Required("forecast"): [forecast_item_schema],
    }
)

HA_API_WEATHER_DATA = Schema(
    {
        Required("id"): Coerce(int),
        Required("type"): str,
        Required("event"): event_schema,
    }
)


@dataclass
class HomeAssistantAPI:
    """Home Assistant API interface."""

    host: InitVar[str]
    token: InitVar[str]
    entity_id: str
    _hass_url: str = field(init=False, repr=False)
    _auth_headers: dict[str, str] = field(default_factory=dict, init=False, repr=False)
    _data_headers: dict[str, Union[str, int, float]] = field(
        default_factory=dict, init=False, repr=False
    )

    def __post_init__(self, host: str, token: str) -> None:
        """Initialize the Home Assistant API interface."""

        if not len(self.entity_id.split(".")) == 2:
            raise ValueError("Invalid entity_id: %s. Must use format 'weather.<name>'")
        if not self.entity_id.startswith("weather."):
            raise ValueError("Only weather entities are supported")

        self._hass_url = f"ws://{host}/api/websocket"
        _LOGGER.debug("Initializing HA API at %s", self._hass_url)

        self._auth_headers = {
            "type": "auth",
            "access_token": token,
        }
        self._data_headers = {
            "id": -1,
            "type": "weather/subscribe_forecast",
            "entity_id": self.entity_id,
            "forecast_type": "hourly",
        }

    @property
    def url(self) -> str:
        """Return the Home Assistant API URL."""
        return self._hass_url

    @property
    def online(self) -> bool:
        """Return whether the Home Assistant API is online."""
        try:
            with connect(self.url) as websocket:
                self._authenticate(websocket)
                return True
        except Exception:
            return False

    @property
    def data_headers(self) -> dict[str, Union[str, int]]:
        """Return the data headers."""
        return {
            "id": random.randint(0, 100000),
            "type": "weather/subscribe_forecast",
            "entity_id": self.entity_id,
            "forecast_type": "hourly",
        }

    def _authenticate(self, websocket: Connection) -> None:
        """Authenticate with the Home Assistant API."""
        reply = json.loads(websocket.recv())
        _LOGGER.debug("Received: %s", reply)
        if not reply["type"] == "auth_required":
            _LOGGER.error("Auth failed. Reply: %s", reply)
            raise ValueError("Authentication failed")
        websocket.send(json.dumps(self._auth_headers))
        reply = json.loads(websocket.recv())
        _LOGGER.debug("Received: %s", reply)
        if not reply["type"] == "auth_ok":
            _LOGGER.error("Auth failed. Reply: %s", reply)
            raise ValueError("Authentication failed")

    @property
    def forecast(self) -> list[dict[str, Union[str, int, float]]]:
        """Get the weather forecast."""
        with connect(self._hass_url) as websocket:
            self._authenticate(websocket)
            websocket.send(json.dumps(self.data_headers))

            # first reply: {..., 'success': True, 'result': None}
            status: Dict[str, Union[bool, typing.Any]] = json.loads(websocket.recv())
            if not status.get("success", False):
                _LOGGER.error("Data request failed. Reply: %s", status)
                raise ValueError("Data request failed")

            # second reply contains the forecast data, using the format:
            # {..., 'event': {'type': 'hourly', 'forecast': [{x}, {x}, ...]}}
            reply: Dict[str, Union[bool, typing.Any]] = json.loads(websocket.recv())
            if not isinstance(reply, dict):
                _LOGGER.error("Data request failed. Reply: %s", reply)
                raise ValueError("Data request failed")

            # validate the reply with voluptuous
            HA_API_WEATHER_DATA(reply)
            forecast = reply["event"]["forecast"]
            if not isinstance(forecast, list):
                _LOGGER.error("Invalid forecast data: %s", forecast)
                raise ValueError("Invalid forecast data")
            return forecast
