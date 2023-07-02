"""Home Assistant API interface for PVCast. Handles the communication with the Home Assistant API."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from urllib.parse import urljoin

from requests import Response, get, post

_LOGGER = logging.getLogger(__name__)


@dataclass
class HassAPI:
    """Home Assistant API interface for PVCast."""

    hass_url: str
    token: str
    timeout: int = field(default=5)
    _headers: dict = field(default_factory=dict)

    def __post_init__(self):
        self._headers = {
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json",
        }

        # check if the API is online
        if not self.online:
            raise ConnectionError("Home Assistant API is not reachable.")

    @property
    def url(self) -> str:
        """Return the url to the Home Assistant API."""
        return urljoin(self.hass_url, "api/")

    @property
    def headers(self) -> dict:
        """Return the headers to the Home Assistant API."""
        return self._headers

    @property
    def online(self) -> bool:
        """Return True if the Home Assistant API is online.

        Equivalent curl command:
        curl \
            -H "Authorization: Bearer TOKEN" \
            -H "Content-Type: application/json" http://localhost:8123/api/
        """
        response = get(self.url, headers=self.headers, timeout=self.timeout)
        return response.ok
