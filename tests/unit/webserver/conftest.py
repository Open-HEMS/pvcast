"""Webserver specific pytest setup."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from pvcast.config.configreader import ConfigReader
from pvcast.webserver.app import app
from pvcast.webserver.routers.dependencies import (
    get_config_reader,
    get_pv_system_mngr,
    get_weather_sources,
)
from tests.const import TEST_CONF_PATH_NO_SEC

if TYPE_CHECKING:
    from pvcast.model.model import PVSystemManager
    from pvcast.weather.weather import WeatherAPI


@pytest.fixture(scope="session")
def client_base() -> TestClient:
    """Return basic test client."""
    return TestClient(app)


@pytest.fixture
def client(weather_api_fix_loc: WeatherAPI, pv_sys_mngr: PVSystemManager) -> TestClient:
    """Overwrite the weather sources dependency with a mock."""
    app.dependency_overrides[get_weather_sources] = lambda: (weather_api_fix_loc,)
    app.dependency_overrides[get_pv_system_mngr] = lambda: pv_sys_mngr
    app.dependency_overrides[get_config_reader] = lambda: ConfigReader(
        TEST_CONF_PATH_NO_SEC
    )
    return TestClient(app)


@pytest.fixture
def start_end() -> dict[str, str]:
    """Get the start and end datetime."""
    return {"start": "2024-01-17T00:00:00Z", "end": "2024-01-17T23:59:00Z"}


@pytest.fixture(scope="session")
def headers() -> dict[str, str]:
    """Get the headers."""
    return {"Content-Type": "application/json", "accept": "application/json"}
