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

import json
from types import MappingProxyType
from typing import Any

import pandas as pd
import pytest
from pvlib.location import Location

from pvcast.model.model import PVSystemManager

from .const import LOC_AUS, LOC_EUW, LOC_USW


@pytest.fixture()
def weather_df() -> pd.DataFrame:
    """Fixture for a basic pvlib input weather dataframe."""
    # fmt: off
    data = {
        'datetime': [
            '2023-06-17 00:00:00+00:00', '2023-06-17 01:00:00+00:00', '2023-06-17 02:00:00+00:00',
            '2023-06-17 03:00:00+00:00', '2023-06-17 04:00:00+00:00', '2023-06-17 05:00:00+00:00',
            '2023-06-17 06:00:00+00:00', '2023-06-17 07:00:00+00:00', '2023-06-17 08:00:00+00:00',
            '2023-06-17 09:00:00+00:00', '2023-06-17 10:00:00+00:00', '2023-06-17 11:00:00+00:00',
            '2023-06-17 12:00:00+00:00', '2023-06-17 13:00:00+00:00', '2023-06-17 14:00:00+00:00',
            '2023-06-17 15:00:00+00:00', '2023-06-17 16:00:00+00:00', '2023-06-17 17:00:00+00:00',
            '2023-06-17 18:00:00+00:00', '2023-06-17 19:00:00+00:00', '2023-06-17 20:00:00+00:00',
            '2023-06-17 21:00:00+00:00', '2023-06-17 22:00:00+00:00', '2023-06-17 23:00:00+00:00',
            '2023-06-18 00:00:00+00:00'
        ],
        'cloud_cover': [
            38.0, 35.0, 27.0, 39.0, 49.0, 83.0, 50.0, 7.0, 14.0, 28.0, 0.0, 3.0, 0.0,
            5.0, 25.0, 10.0, 46.0, 56.0, 45.0, 51.0, 95.0, 94.0, 89.0, 91.0, 91.0
        ],
        'wind_speed': [
            4.91744, 4.47040, 4.47040, 4.02336, 4.91744, 4.47040, 4.02336, 3.57632,
            3.57632, 3.57632, 3.57632, 3.57632, 3.57632, 3.57632, 4.02336, 4.02336,
            4.47040, 4.47040, 4.02336, 3.57632, 3.12928, 3.12928, 2.68224, 2.68224, 2.68224
        ],
        'temperature': [
            28.0, 23.0, 22.0, 20.0, 21.0, 20.0, 20.0, 19.0, 19.0, 18.0, 18.0, 17.0,
            17.0, 17.0, 17.0, 18.0, 20.0, 21.0, 23.0, 24.0, 25.0, 25.0, 25.0, 25.0, 25.0
        ],
        'humidity': [
            28.0, 23.0, 30.0, 36.0, 44.0, 49.0, 49.0, 48.0, 51.0, 52.0, 56.0, 61.0,
            64.0, 65.0, 64.0, 61.0, 55.0, 52.0, 45.0, 39.0, 34.0, 34.0, 36.0, 36.0, 36.0
        ],
        'dni': [
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0, 8.0, 16.0, 25.0, 33.0, 40.0, 46.0,
            51.0, 55.0, 58.0, 60.0, 61.0, 61.0, 60.0, 58.0, 55.0, 51.0, 46.0, 40.0
        ],
        'dhi': [
            0.0, 0.0, 0.0, 0.0, 0.0, 2.0, 8.0, 16.0, 25.0, 33.0, 40.0, 46.0, 51.0,
            55.0, 58.0, 60.0, 61.0, 61.0, 60.0, 58.0, 55.0, 51.0, 46.0, 40.0, 33.0
        ],
        'ghi': [
            0.0, 0.0, 0.0, 0.0, 0.0, 2.0, 8.0, 16.0, 25.0, 33.0, 40.0, 46.0, 51.0,
            55.0, 58.0, 60.0, 61.0, 61.0, 60.0, 58.0, 55.0, 51.0, 46.0, 40.0, 33.0
        ],
    }
    # fmt: on

    df = pd.DataFrame(data)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.set_index("datetime")
    return df


@pytest.fixture(scope="session")
def pd_time_aliases() -> dict[str, list[str]]:
    """Fixture for pandas time aliases."""
    return {
        "1H": ["H"],
        "30Min": ["30T"],
        "15Min": ["15T"],
        "1W": ["W"],
    }


@pytest.fixture(scope="function")
def ha_weather_data() -> dict[str, Any]:
    """Load the weather test data."""
    with open("tests/ha_weather_data.json") as json_file:
        weather_data: dict[str, Any] = json.load(json_file)
        # set to 1 to easily test if the data is correctly converted
        for forecast in weather_data["attributes"]["forecast"]:
            forecast["wind_speed"] = 1.0
            forecast["temperature"] = 1.0
        return weather_data


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
