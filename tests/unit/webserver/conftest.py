"""Webserver specific pytest setup."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from pvcast.webserver.app import app
from pvcast.webserver.routers.dependencies import (
    get_pv_system_mngr,
    get_weather_sources,
)

if TYPE_CHECKING:
    from pvcast.model.model import PVSystemManager
    from pvcast.weather.weather import WeatherAPI


@pytest.fixture
def client_weather(
    weather_api_fix_loc: WeatherAPI, pv_sys_mngr: PVSystemManager
) -> TestClient:
    """Overwrite the weather sources dependency with a mock."""
    app.dependency_overrides[get_weather_sources] = lambda: (weather_api_fix_loc,)
    app.dependency_overrides[get_pv_system_mngr] = lambda: pv_sys_mngr
    return TestClient(app)


@pytest.fixture
def client() -> TestClient:
    """Get the base test client."""
    return TestClient(app)


@pytest.fixture
def start_end() -> dict[str, str]:
    """Get the start and end datetime."""
    return {"start": "2024-01-17T00:00:00Z", "end": "2024-01-17T23:59:00Z"}


@pytest.fixture(scope="session")
def headers() -> dict[str, str]:
    """Get the headers."""
    return {"Content-Type": "application/json", "accept": "application/json"}
