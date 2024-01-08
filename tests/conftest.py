#   ---------------------------------------------------------------------------------
#   Copyright (c) Microsoft Corporation. All rights reserved.
#   Licensed under the MIT License. See LICENSE in project root for information.
#   ---------------------------------------------------------------------------------
"""
This is a configuration file for pytest containing customizations and fixtures.

In VSCode, Code Coverage is recorded in config.xml. Delete this file to reset reporting.

See https://stackoverflow.com/questions/34466027/in-pytest-what-is-the-use-of-conftest-py-files
"""

from __future__ import annotations

import datetime as dt
from types import MappingProxyType
from typing import Any

import numpy as np
import polars as pl
import pytest
from pvlib.location import Location

from pvcast.model.model import PVSystemManager

from .const import LOC_AUS, LOC_EUW, LOC_USW


@pytest.fixture()
def weather_df() -> pl.DataFrame:
    """Fixture for a basic pvlib input weather dataframe."""
    n_points = int(dt.timedelta(days=2) / dt.timedelta(hours=1))
    return pl.DataFrame(
        {
            "datetime": pl.datetime_range(
                dt.date(2022, 1, 1),
                dt.date(2022, 1, 3),
                "1h",
                eager=True,
                time_zone="UTC",
            )[0:n_points],
            "cloud_cover": list(np.linspace(0, 100, n_points)),
            "wind_speed": list(np.linspace(0, 10, n_points)),
            "temperature": list(np.linspace(0, 40, n_points)),
            "humidity": list(np.linspace(0, 100, n_points)),
            "dni": list(np.linspace(0, 1000, n_points)),
            "dhi": list(np.linspace(0, 1000, n_points)),
            "ghi": list(np.linspace(0, 1000, n_points)),
        }
    )


@pytest.fixture(scope="session")
def clearoutside_html_page() -> str:
    """Load the clearoutside html page."""
    with open("tests/clearoutside.txt") as html_file:
        return html_file.read()


@pytest.fixture(params=[LOC_EUW, LOC_USW, LOC_AUS])
def location(request: pytest.FixtureRequest) -> Location:
    """Fixture that creates a location."""
    return Location(*request.param)


@pytest.fixture
def altitude() -> float:
    """Fixture that creates an altitude."""
    return 10.0


@pytest.fixture(scope="session")
def valid_freqs() -> tuple[str, ...]:
    """Fixture for valid frequency strings."""
    return ("A", "M", "1W", "1D", "1H", "30Min", "15Min")


string_system = [
    MappingProxyType(
        {
            "name": "EastWest",
            "inverter": "SolarEdge_Technologies_Ltd___SE4000__240V_",
            "microinverter": False,
            "arrays": [
                {
                    "name": "East",
                    "tilt": 30,
                    "azimuth": 90,
                    "modules_per_string": 4,
                    "strings": 1,
                    "module": "Trina_Solar_TSM_330DD14A_II_",
                },
                {
                    "name": "West",
                    "tilt": 30,
                    "azimuth": 270,
                    "modules_per_string": 8,
                    "strings": 1,
                    "module": "Trina_Solar_TSM_330DD14A_II_",
                },
            ],
        }
    ),
    MappingProxyType(
        {
            "name": "South",
            "inverter": "SolarEdge_Technologies_Ltd___SE4000__240V_",
            "microinverter": False,
            "arrays": [
                {
                    "name": "South",
                    "tilt": 30,
                    "azimuth": 180,
                    "modules_per_string": 8,
                    "strings": 1,
                    "module": "Trina_Solar_TSM_330DD14A_II_",
                }
            ],
        }
    ),
]

micro_system = [
    MappingProxyType(
        {
            "name": "EastWest",
            "inverter": "Enphase_Energy_Inc___IQ7X_96_x_ACM_US__240V_",
            "microinverter": True,
            "arrays": [
                {
                    "name": "zone_1_schuin",
                    "tilt": 30,
                    "azimuth": 90,
                    "modules_per_string": 5,
                    "strings": 1,
                    "module": "JA_Solar_JAM72S01_385_PR",
                },
                {
                    "name": "zone_2_plat",
                    "tilt": 15,
                    "azimuth": 160,
                    "modules_per_string": 8,
                    "strings": 1,
                    "module": "JA_Solar_JAM72S01_385_PR",
                },
            ],
        }
    )
]


@pytest.fixture(params=[string_system, micro_system])
def basic_config(request: pytest.FixtureRequest) -> list[MappingProxyType[str, Any]]:
    var = request.param
    if isinstance(var, list):
        return var
    raise ValueError("basic_config fixture is not a list")


@pytest.fixture
def pv_sys_mngr(
    basic_config: list[MappingProxyType[str, Any]], location: Location, altitude: float
) -> PVSystemManager:
    return PVSystemManager(
        basic_config, lat=location.latitude, lon=location.longitude, alt=altitude
    )


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """
    Add integration marker to all tests that use the homeassistant_api_setup fixture.
    """
    for item in items:
        if "homeassistant_api_setup" in getattr(item, "fixturenames", ()):
            item.add_marker("integration")
