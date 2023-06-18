"""Test the weather module."""
from __future__ import annotations

import json

import pytest
from const import LOC_EUW, LOC_USW
from pandas import DataFrame, Timedelta, to_datetime
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

    @pytest.fixture(params=["1h", "30min", "15min"])
    def freq(self, request):
        return Timedelta(request.param)

    @pytest.fixture(params=[1, 2, 3])
    # @pytest.fixture(params=[1])
    def max_forecast_day(self, request):
        return Timedelta(days=request.param)

    def test_weather_get_weather(self, clear_outside_api: WeatherAPIClearOutside):
        """Test the get_weather function."""
        freq = "1h"
        weather = clear_outside_api.get_weather()
        assert isinstance(weather, DataFrame)
        assert weather.index.freq == freq
        assert not weather.isna().values.any()
        n_rows = weather.shape[0]
        assert n_rows % (Timedelta(hours=24) / Timedelta(freq)) % 1 == 0

    def test_weather_get_weather_freq(self, clear_outside_api: WeatherAPIClearOutside, freq):
        """Test the get_weather function with a number of higher data frequencies."""
        clear_outside_api.freq_output = freq
        weather = clear_outside_api.get_weather()
        assert isinstance(weather, DataFrame)
        assert weather.index.freq == freq
        assert not weather.isna().values.any()
        n_rows = weather.shape[0]
        assert n_rows % (Timedelta(hours=24) / Timedelta(freq)) % 1 == 0

    def test_weather_get_weather_max_days(self, clear_outside_api: WeatherAPIClearOutside, max_forecast_day):
        """Test the get_weather function with a number of higher data frequencies."""
        freq = "1h"
        clear_outside_api.freq_output = Timedelta(freq)
        clear_outside_api.max_forecast_days = max_forecast_day
        weather = clear_outside_api.get_weather()
        assert isinstance(weather, DataFrame)
        assert weather.index.freq == freq
        assert not weather.isna().values.any()
        n_rows = weather.shape[0]
        assert n_rows % (Timedelta(hours=24) / Timedelta(freq)) % 1 == 0
        assert n_rows <= max_forecast_day / Timedelta(freq)
        assert weather.index[0] == clear_outside_api.start_forecast
        assert weather.index[-1] == clear_outside_api.end_forecast

    def test_weather_data_cache(self, clear_outside_api: WeatherAPIClearOutside):
        """Test the get_weather function."""

        # get first weather data object
        weather1 = clear_outside_api.get_weather()
        assert isinstance(weather1, DataFrame)
        assert weather1.index[0] == clear_outside_api.start_forecast
        assert weather1.index[-1] == clear_outside_api.end_forecast
        last_update1 = clear_outside_api._last_update

        # get second weather data object, should see that it is cached data
        weather2 = clear_outside_api.get_weather()
        assert isinstance(weather2, DataFrame)
        last_update2 = clear_outside_api._last_update
        assert last_update1 == last_update2
        assert weather2.index[0] == clear_outside_api.start_forecast
        assert weather2.index[-1] == clear_outside_api.end_forecast

    def test_weather_data_live(self, clear_outside_api: WeatherAPIClearOutside):
        """Test the get_weather function."""

        # get first weather data object
        weather1 = clear_outside_api.get_weather()
        assert isinstance(weather1, DataFrame)
        assert weather1.index[0] == clear_outside_api.start_forecast
        assert weather1.index[-1] == clear_outside_api.end_forecast
        last_update1 = clear_outside_api._last_update

        # get second weather data object, should see that it is live data
        weather2 = clear_outside_api.get_weather(live=True)
        assert isinstance(weather2, DataFrame)
        assert weather2.index[0] == clear_outside_api.start_forecast
        assert weather2.index[-1] == clear_outside_api.end_forecast
        last_update2 = clear_outside_api._last_update
        assert last_update1 != last_update2
