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
from pathlib import Path

import pytest

from pvcast.config.configreader import ConfigReader
from pvcast.weather.clearoutside import WeatherAPIClearOutside

LOC_EUW = (52.3585, 4.8810, 0.0)
LOC_USW = (40.6893, -74.0445, 0.0)
LOC_AUS = (-31.9741, 115.8517, 0.0)

TEST_CONF_PATH_SEC = Path(__file__).parent.parent / "tests" / "test_config_sec.yaml"
TEST_CONF_PATH_NO_SEC = Path(__file__).parent.parent / "tests" / "test_config_no_sec.yaml"
TEST_CONF_PATH_ERROR = Path(__file__).parent.parent / "tests" / "test_config_error.yaml"
TEST_SECRETS_PATH = Path(__file__).parent.parent / "tests" / "test_secrets.yaml"


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


@pytest.fixture()
def configreader_secfile_sectags():
    """Fixture for the configreader."""
    return ConfigReader(TEST_CONF_PATH_SEC, TEST_SECRETS_PATH)


@pytest.fixture()
def configreader_no_secfile_no_sectags():
    """Fixture for the configreader initialized without a secrets file and no !secret tags in config."""
    return ConfigReader(config_file_path=TEST_CONF_PATH_NO_SEC)


@pytest.fixture()
def configreader_no_secfile_sectags():
    """
    Fixture for the configreader initialized without a secrets file but with !secret tags in config.
    This should raise an exception.
    """
    return ConfigReader(config_file_path=TEST_CONF_PATH_SEC)


@pytest.fixture()
def configreader_wrong_timezone():
    """
    Fixture for the configreader initialized with a timezone that does not exist.
    This should raise an exception.
    """
    return ConfigReader(config_file_path=TEST_CONF_PATH_ERROR)
