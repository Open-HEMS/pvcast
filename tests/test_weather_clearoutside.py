"""Test the weather module."""
from __future__ import annotations

import json

import pytest
from const import LOC_EUW, LOC_USW
from pandas import DataFrame, to_datetime
from pvlib.location import Location

from pvcast.weather.clearoutside import WeatherAPIClearOutside


class TestWeatherClearOutside:
    """Test the clear outside weather module."""

    @pytest.fixture(params=[LOC_EUW, LOC_USW])
    def clear_outside_api(self, request):
        """Fixture for the Clear Outside weather API with no data."""
        lat = request.param[0]
        lon = request.param[1]
        alt = request.param[2]
        tz = request.param[3]

        return WeatherAPIClearOutside(location=Location(lat, lon, tz, alt))

    @pytest.fixture()
    def weather_df(self):
        """Fixture for a basic weather dataframe."""
        with open(WEATHER_DATA_PATH) as f:
            data = json.load(f)
        df = DataFrame(data).transpose()
        df.index = to_datetime(df.index, unit="ms")
        print(df.head())
        return df

    def test_weather_data_cache(self, clear_outside_api: WeatherAPIClearOutside):
        """Test the get_weather function."""

        # get first weather data object
        weather1 = clear_outside_api.get_weather()
        assert isinstance(weather1, DataFrame)
        last_update1 = clear_outside_api._last_update

        # get second weather data object, should see that it is cached data
        weather2 = clear_outside_api.get_weather()
        assert isinstance(weather2, DataFrame)
        last_update2 = clear_outside_api._last_update
        assert last_update1 == last_update2

    def test_weather_data_live(self, clear_outside_api: WeatherAPIClearOutside):
        """Test the get_weather function."""

        # get first weather data object
        weather1 = clear_outside_api.get_weather()
        assert isinstance(weather1, DataFrame)
        last_update1 = clear_outside_api._last_update

        # get second weather data object, should see that it is live data
        weather2 = clear_outside_api.get_weather(live=True)
        assert isinstance(weather2, DataFrame)
        last_update2 = clear_outside_api._last_update
        assert last_update1 != last_update2
        print(weather2)
