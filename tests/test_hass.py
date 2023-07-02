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
