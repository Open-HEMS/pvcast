"""Home Assistant API interface. Handles the communication with the Home Assistant API."""

from __future__ import annotations

import json
import logging
import secrets
import typing
from dataclasses import InitVar, dataclass, field

from voluptuous import All, Coerce, MultipleInvalid, Range, Required, Schema
from websockets.sync.client import Connection, connect  # type: ignore[attr-defined]

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
    _data_headers: dict[str, str | int | float] = field(
        default_factory=dict, init=False, repr=False
    )

    def __post_init__(self, host: str, token: str) -> None:
        """Initialize the Home Assistant API interface."""
        if len(self.entity_id.split(".")) != 2:
            msg = "Invalid entity_id: %s. Must use format 'weather.<name>'"
            raise ValueError(msg)
        if not self.entity_id.startswith("weather."):
            msg = "Only weather entities are supported"
            raise ValueError(msg)

        # strip http(s):// from host if present and add ws://
        host_stripped = host.replace("http://", "").replace("https://", "")
        self._hass_url = f"ws://{host_stripped}/api/websocket"
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
        with connect(self.url) as websocket:
            return self._authenticate(websocket)

    @property
    def data_headers(self) -> dict[str, str | int]:
        """Return the data headers."""
        return {
            "id": secrets.randbelow(100000),
            "type": "weather/subscribe_forecast",
            "entity_id": self.entity_id,
            "forecast_type": "hourly",
        }

    def _authenticate(self, websocket: Connection) -> bool:
        """Authenticate with the Home Assistant API.

        Returns True if authentication was successful, False otherwise.
        """
        reply = json.loads(websocket.recv())
        _LOGGER.debug("Received auth reply from HA: %s", reply)
        if reply["type"] != "auth_required":
            _LOGGER.error("Auth failed. Reply: %s", reply)
            return False
        websocket.send(json.dumps(self._auth_headers))
        reply = json.loads(websocket.recv())
        _LOGGER.debug("Received: %s", reply)
        if reply["type"] != "auth_ok":
            _LOGGER.error("Auth failed. Reply: %s", reply)
            return False
        return True

    @property
    def forecast(self) -> list[dict[str, str | int | float]]:
        """Get the weather forecast."""
        _LOGGER.info("Requesting data from %s", self._hass_url)
        with connect(self._hass_url) as websocket:
            self._authenticate(websocket)
            websocket.send(json.dumps(self.data_headers))

            # first reply: {..., 'success': True, 'result': None}
            status: dict[str, bool | typing.Any] = json.loads(websocket.recv())
            if not status.get("success", False):
                _LOGGER.error("Data request failed. Reply: %s", status)
                msg = "Data request failed"
                raise ValueError(msg)

            # second reply contains the forecast data, using the format:
            # {..., 'event': {'type': 'hourly', 'forecast': [{x}, {x}, ...]}}
            reply: dict[str, bool | typing.Any] = json.loads(websocket.recv())
            if not isinstance(reply, dict):
                _LOGGER.error("Data request failed. Reply: %s", reply)
                msg = "Data request failed"
                raise TypeError(msg)

            # validate the reply with voluptuous
            try:
                HA_API_WEATHER_DATA(reply)
            except MultipleInvalid as exc:
                _LOGGER.exception("Invalid data received")
                msg = "Invalid data received"
                raise ValueError(msg) from exc

            # extract the forecast data from the reply
            forecast = reply["event"]["forecast"]
            if not isinstance(forecast, list):
                _LOGGER.error("Invalid forecast data: %s", forecast)
                msg = "Invalid forecast data"
                raise TypeError(msg)
            return forecast
