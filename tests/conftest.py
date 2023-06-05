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

from dataclasses import replace
import pytest
import unittest.mock as mock

from pvcast.weather.weather import WeatherAPIClearOutside

LOC_EUW = (52.3585, 4.8810, 0.0)
LOC_USW = (40.6893, -74.0445, 0.0)
LOC_AUS = (-31.9741, 115.8517, 0.0)


# check with different lat/lon/alt
@pytest.fixture(params=[LOC_EUW, LOC_USW, LOC_AUS])
def weather_co(request):
    """Fixture for the Clear Outside weather API."""
    return WeatherAPIClearOutside(*request.param)


@pytest.fixture()
def weather_co_wrong_url():
    """Fixture for the Clear Outside weather API with no data."""
    obj = WeatherAPIClearOutside(*LOC_EUW)

    # set the url to a wrong url (require replace() bc dataclass is frozen)
    return replace(obj, url_base="https://clearoutside.com/wrongcast/")


@pytest.fixture()
def weather_co_too_many_req():
    """Fixture for clear outside response 429 (too many requests)."""
    # set the url to a wrong url (require replace() bc dataclass is frozen)
    obj = replace(WeatherAPIClearOutside(*LOC_EUW), url_base="http://httpbin.org/status/429", format_url=False)
    return obj
