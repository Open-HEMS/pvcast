#   ---------------------------------------------------------------------------------
#   Copyright (c) Microsoft Corporation. All rights reserved.
#   Licensed under the MIT License. See LICENSE in project root for information.
#   ---------------------------------------------------------------------------------
"""This is a sample python file for testing functions from the source code."""
from __future__ import annotations


class TestWeather:
    """Test the weather module."""

    def test_get_weather_co(self, weather_co):
        """Test the get_weather function."""
        weather = weather_co.get_weather()
        assert isinstance(weather, dict)
