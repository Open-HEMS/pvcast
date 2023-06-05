#   ---------------------------------------------------------------------------------
#   Copyright (c) Microsoft Corporation. All rights reserved.
#   Licensed under the MIT License. See LICENSE in project root for information.
#   ---------------------------------------------------------------------------------
"""This is a sample python file for testing functions from the source code."""
from __future__ import annotations

import pytest

from pvcast.weather.weather import WeatherAPIErrorNoData, WeatherAPIErrorTooManyReq
from pandas import DataFrame


class TestWeatherCO:
    """Test the clear outside weather module."""

    def test_get_weather_co(self, weather_co):
        """Test the get_weather function."""
        weather = weather_co.get_weather()
        assert isinstance(weather, DataFrame)

    def test_get_weather_wrong_url(self, weather_co_wrong_url):
        """Test the get_weather function."""
        with pytest.raises(WeatherAPIErrorNoData) as excinfo:
            weather_co_wrong_url.get_weather()
        assert "No weather data available" in str(excinfo.value.message)

    def test_get_weather_too_many_req(self, weather_co_too_many_req):
        """Test the get_weather function."""
        with pytest.raises(WeatherAPIErrorTooManyReq) as excinfo:
            weather_co_too_many_req.get_weather()
        assert "Too many requests" in str(excinfo.value.message)
