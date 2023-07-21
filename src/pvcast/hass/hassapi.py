"""Home Assistant API interface for PVCast. Handles the communication with the Home Assistant API."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from urllib.parse import urljoin

from requests import Response, get

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
        """Return True if the Home Assistant API is online."""
        response: Response = get(self.url, headers=self.headers, timeout=self.timeout)
        _LOGGER.debug("Home Assistant API online: %s", response.ok)
        return response.ok

    def get_entity_state(self, entity_id: str) -> dict:
        """Get the state object for specified entity_id. Returns None if entity not found."""
        if not len(entity_id.split(".")) == 2:
            raise ValueError(f"Invalid entity_id: {entity_id}")
        url = urljoin(self.url, f"states/{entity_id}")
        _LOGGER.debug("Getting entity %s state from %s", entity_id, url)
        response: Response = get(url, headers=self.headers, timeout=self.timeout)

        # if we receive a 404 the entity does not exist and we can't continue
        if response.status_code == 404:
            raise ValueError(f"Entity {entity_id} not found.")
        if not response.ok:
            raise ConnectionError(f"Error while getting entity {entity_id}: {response.reason}")
        return response
