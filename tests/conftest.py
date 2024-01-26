#   ---------------------------------------------------------------------------------
#   Copyright (c) Microsoft Corporation. All rights reserved.
#   Licensed under the MIT License. See LICENSE in project root for information.
#   ---------------------------------------------------------------------------------
"""Configuration file for pytest containing customizations and fixtures.

In VSCode, Code Coverage is recorded in config.xml. Delete this file to reset reporting.

See https://stackoverflow.com/questions/34466027/in-pytest-what-is-the-use-of-conftest-py-files
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np
import polars as pl
import pytest
import yaml
from pvlib.location import Location

from pvcast.model.model import PVPlantModel, PVSystemManager
from pvcast.weather.weather import WeatherAPI

from .const import LOC_AUS, LOC_EUW, LOC_USW, MOCK_WEATHER_API

SECRETS_FILE_PATH_TEST = Path("tests/data/secrets.yaml")
CONFIG_FILE_PATH_TEST = Path("tests/data/config.yaml")
os.environ["SECRETS_FILE_PATH"] = str(SECRETS_FILE_PATH_TEST)
os.environ["CONFIG_FILE_PATH"] = str(CONFIG_FILE_PATH_TEST)


@pytest.fixture(scope="session")
def test_url() -> str:
    """Fixture for a test url."""
    return "http://fakeurl.com/"


@pytest.fixture
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
            "cloud_cover": list(np.linspace(20, 60, n_points)),
            "wind_speed": list(np.linspace(0, 10, n_points)),
            "temperature": list(np.linspace(10, 25, n_points)),
            "humidity": list(np.linspace(0, 100, n_points)),
            "dni": list(np.linspace(0, 1000, n_points)),
            "dhi": list(np.linspace(0, 1000, n_points)),
            "ghi": list(np.linspace(0, 1000, n_points)),
        }
    )


@pytest.fixture(scope="session")
def clearoutside_html_page() -> str:
    """Load the clearoutside html page."""
    with Path.open(Path("tests/data/clearoutside.txt")) as html_file:
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
    ),
    MappingProxyType(
        {
            "name": "South",
            "inverter": "Enphase_Energy_Inc___IQ7X_96_x_ACM_US__240V_",
            "microinverter": True,
            "arrays": [
                {
                    "name": "zone_1_schuin",
                    "tilt": 30,
                    "azimuth": 180,
                    "modules_per_string": 8,
                    "strings": 1,
                    "module": "JA_Solar_JAM72S01_385_PR",
                }
            ],
        }
    ),
]


@pytest.fixture(params=[string_system, micro_system])
def basic_config(request: pytest.FixtureRequest) -> list[MappingProxyType[str, Any]]:
    """Fixture that creates a basic configuration."""
    var = request.param
    if isinstance(var, list):
        return var
    msg = "basic_config fixture is not a list"
    raise ValueError(msg)


@pytest.fixture
def pv_sys_mngr(
    basic_config: list[MappingProxyType[str, Any]], location: Location, altitude: float
) -> PVSystemManager:
    """Fixture that creates a PVSystemManager."""
    return PVSystemManager(
        basic_config, lat=location.latitude, lon=location.longitude, alt=altitude
    )


@pytest.fixture
def pv_plant_model(
    basic_config: list[MappingProxyType[str, Any]], location: Location
) -> PVPlantModel:
    """Fixture that creates a PVPlantModel."""
    inv_params = {
        "index": basic_config[0]["inverter"],
        "Vac": 240,
        "Pso": 1.235644,
        "Paco": 315.0,
        "Pdco": 322.960602,
        "Vdco": 60.0,
        "C0": -2.8e-05,
        "C1": -1.6e-05,
        "C2": 0.003418,
        "C3": -0.036432,
        "Pnt": 0.0945,
        "Vdcmax": 64.0,
        "Idcmax": 5.382677,
        "Mppt_low": 53.0,
        "Mppt_high": 64.0,
        "CEC_Date": "10/15/2018",
        "CEC_Type": "Utility Interactive",
        "CEC_hybrid": None,
    }

    mod_params = {
        "index": basic_config[0]["arrays"][0]["module"],
        "Technology": "Mono-c-Si",
        "Bifacial": 0,
        "STC": 385.1724,
        "PTC": 357.9,
        "A_c": 1.88,
        "Length": None,
        "Width": None,
        "N_s": 72,
        "I_sc_ref": 10.11,
        "V_oc_ref": 48.98,
        "I_mp_ref": 9.56,
        "V_mp_ref": 40.29,
        "alpha_sc": 0.004246,
        "beta_oc": -0.132246,
        "T_NOCT": 44.91,
        "a_ref": 1.849046,
        "I_L_ref": 10.116335,
        "I_o_ref": 3.138217e-11,
        "R_s": 0.317577,
        "R_sh_ref": 506.821045,
        "Adjust": 10.237704,
        "gamma_r": -0.369,
        "BIPV": "N",
        "Version": "SAM 2018.11.11 r2",
        "Date": "1/3/2019",
        "Manufacturer": None,
    }

    return PVPlantModel(
        basic_config[0],
        location=location,
        inv_param=pl.LazyFrame(inv_params),
        mod_param=pl.LazyFrame(mod_params),
    )


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Add integration marker to all tests that use the homeassistant_api_setup fixture."""
    for item in items:
        if "homeassistant_api_setup" in getattr(item, "fixturenames", ()):
            item.add_marker("integration")


# mock for WeatherAPI class
class MockWeatherAPI(WeatherAPI):
    """Mock the WeatherAPI class."""

    def __init__(
        self, location: Location, url: str, data: pl.DataFrame, **kwargs: Any
    ) -> None:
        """Initialize the mock class."""
        super().__init__(location, url, freq_source=dt.timedelta(minutes=60), **kwargs)
        self.url = url
        self.data = data

    def retrieve_new_data(self) -> pl.DataFrame:
        """Retrieve new data from the API."""
        return self.data


@pytest.fixture
def weather_api(
    location: Location, request: pytest.FixtureRequest, test_url: str
) -> WeatherAPI:
    """Get a weather API object."""
    return MockWeatherAPI(
        location=location, url=test_url, data=request.param, name=MOCK_WEATHER_API
    )


@pytest.fixture
def weather_api_fix_loc(request: pytest.FixtureRequest, test_url: str) -> WeatherAPI:
    """Get a weather API object."""
    return MockWeatherAPI(
        location=Location(51.2, 6.1, "UTC", 0),
        url=test_url,
        data=request.param,
        name=MOCK_WEATHER_API,
    )


# create fake test file secrets.yaml when the test suite is run
# this is needed for the configreader to work
def pytest_sessionstart(session: pytest.Session) -> None:  # noqa: ARG001
    """Create a fake secrets.yaml file for testing."""
    secrets = {
        "lat": 51.2,
        "lon": 6.1,
        "alt": 0,
        "long_lived_token": "test_token",
        "time_zone": "UTC",
    }
    if not Path.exists(SECRETS_FILE_PATH_TEST):
        with Path.open(SECRETS_FILE_PATH_TEST, "w") as outfile:
            yaml.dump(secrets, outfile, default_flow_style=False)
