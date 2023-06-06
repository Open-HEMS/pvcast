"""Test the weather module."""
from __future__ import annotations

import pytest
from pandas import DataFrame

from pvcast.weather.weather import WeatherAPIErrorNoData, WeatherAPIErrorTooManyReq


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
