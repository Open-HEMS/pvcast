"""Test the weather module."""
from __future__ import annotations

from pandas import DataFrame


class TestWeather:
    """Test the weather module."""

    def test_get_weather_co(self, weather_co):
        """Test the get_weather function."""
        weather = weather_co.get_weather()
        assert isinstance(weather, DataFrame)
