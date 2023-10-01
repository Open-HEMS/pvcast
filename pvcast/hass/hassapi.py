"""Home Assistant API interface. Handles the communication with the Home Assistant API."""

from __future__ import annotations

import logging
from dataclasses import InitVar, dataclass, field
from urllib.parse import urljoin

import requests
from requests import Response
from requests.adapters import HTTPAdapter, Retry

s = requests.Session()

retries = Retry(total=4, backoff_factor=0.2, backoff_max=5, status_forcelist=[502, 503, 504])

s.mount("http://", HTTPAdapter(max_retries=retries))

_LOGGER = logging.getLogger(__name__)


@dataclass
class HassAPI:
    """Home Assistant API interface."""

    hass_url: str
    token: InitVar[str]
    _headers: dict = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self, token: str):
        self._headers = {
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        }

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
        response: Response = s.get(self.url, headers=self.headers)
        _LOGGER.debug("Home Assistant API online: %s", response.ok)
        return response.ok

    def get_entity_state(self, entity_id: str) -> Response:
        """Get the state object for specified entity_id. Raises ValueError if entity is not found.

        :param entity_id: The entity_id to get the state object for.
        :return: The state object for the specified entity_id.
        """
        url = self._format_entity_url(entity_id)
        response: Response = s.get(url, headers=self.headers)

        # if we receive a 404 the entity does not exist and we can't continue
        if response.status_code == 404:
            raise ValueError(f"Entity {entity_id} not found.")
        if not response.ok:
            raise requests.ConnectionError(f"Error while getting entity {entity_id}: {response.reason}")
        return response

    def post_entity_state(self, entity_id: str, state: dict) -> Response:
        """Post the state object for specified entity_id.

        Response will be something like:

        {
            "entity_id":"sensor.kitchen_temperature",
            "state":"25",
            "attributes":{
                "unit_of_measurement":"°C"
            },
            "last_changed":"2023-07-27T10:33:35.834356+00:00",
            "last_updated":"2023-07-27T10:33:35.834356+00:00",
            "context":{
                "id":"01H6BEJFTTT1W8BJ905B2YS3JA",
                "parent_id":null,
                "user_id":"f20d2b011d0f40c182c676dce72bd6a2"
            }
        }

        :param entity_id: The entity_id to post the state object for.
        :param state: The state object to post.
        :return: The response object.
        """
        url = self._format_entity_url(entity_id)
        response: Response = s.post(url, headers=self.headers, json=state)
        if not response.ok:
            raise requests.ConnectionError(f"Error while posting entity {entity_id}: {response.reason}")
        _LOGGER.debug("Successfully updated/created entity: %s [code:%s]", entity_id, response.status_code)
        return response

    def _format_entity_url(self, entity_id: str) -> str:
        """Format the url to the Home Assistant API for the specified entity_id."""
        if not len(entity_id.split(".")) == 2:
            raise ValueError(f"Invalid entity_id: {entity_id}")
        return urljoin(self.url, f"states/{entity_id}")
