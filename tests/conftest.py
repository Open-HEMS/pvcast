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
import pytest
from pandas import DataFrame, to_datetime


@pytest.fixture()
def weather_df():
    """Fixture for a basic weather dataframe."""
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

    df = DataFrame(data)
    df["datetime"] = to_datetime(df["datetime"])
    df = df.set_index("datetime")
    return df


@pytest.fixture(scope="session")
def pd_time_aliases():
    """Fixture for pandas time aliases."""
    return {
        "1H": ["H"],
        "30Min": ["30T"],
        "15Min": ["15T"],
        "1W": ["W"],
    }


@pytest.fixture
def ha_weather_data(scope="session"):
    """Load the weather test data."""
    with open("tests/ha_weather_data.json") as json_file:
        weather_data: dict = json.load(json_file)
        # set to 1 to easily test if the data is correctly converted
        for forecast in weather_data["attributes"]["forecast"]:
            forecast["wind_speed"] = 1.0
            forecast["temperature"] = 1.0
        return weather_data
