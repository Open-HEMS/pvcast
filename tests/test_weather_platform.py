"""Test all configured weather platforms that inherit from WeatherAPI class."""
from __future__ import annotations

import pytest
from const import LOC_EUW, LOC_USW
from pandas import DataFrame, Timedelta, infer_freq, to_datetime
from pvlib.location import Location

from pvcast.weather.clearoutside import WeatherAPIClearOutside


class TestWeatherPlatform:
    """Test a weather platform that inherits from WeatherAPI class."""

    @pytest.fixture()
    def time_aliases(self, pd_time_aliases):
        return pd_time_aliases

    @pytest.fixture(params=[LOC_EUW, LOC_USW])
    def clear_outside_api(self, request):
        """Fixture for the Clear Outside weather API with no data."""
        return WeatherAPIClearOutside(location=Location(*request.param))

    @pytest.fixture(params=[1, 2, 3])
    def max_forecast_day(self, request):
        return Timedelta(days=request.param)

    def convert_to_df(self, weather):
        """Convert the weather data to a DataFrame."""
        weather = DataFrame.from_dict(weather["data"])
        weather.set_index("datetime", inplace=True)
        weather.index = to_datetime(weather.index)
        return weather

    def test_weather_get_weather(self, clear_outside_api: WeatherAPIClearOutside):
        """Test the get_weather function."""
        weather = clear_outside_api.get_weather()
        assert isinstance(weather, dict)
        weather = self.convert_to_df(weather)
        assert isinstance(weather, DataFrame)
        assert infer_freq(weather.index) == "H"
        assert not weather.isna().values.any()
        n_rows = weather.shape[0]
        assert n_rows % (Timedelta(hours=24) / Timedelta("1h")) == 0

    @pytest.mark.parametrize("freq", ["1H", "30Min", "15Min"])
    def test_weather_get_weather_freq(self, clear_outside_api: WeatherAPIClearOutside, freq, time_aliases):
        """Test the get_weather function with a number of higher data frequencies."""
        clear_outside_api.freq_output = freq
        weather = clear_outside_api.get_weather()
        assert isinstance(weather, dict)
        weather = self.convert_to_df(weather)
        print(weather.tail())
        assert isinstance(weather, DataFrame)
        assert infer_freq(weather.index) in time_aliases[freq]
        assert not weather.isna().values.any()
        assert weather.index[0] == clear_outside_api.start_forecast
        assert weather.index[-1] == clear_outside_api.end_forecast - Timedelta(freq)
        n_rows = weather.shape[0]
        assert n_rows % (Timedelta(hours=24) / Timedelta(freq)) == 0

    def test_weather_get_weather_max_days(
        self, clear_outside_api: WeatherAPIClearOutside, max_forecast_day, time_aliases
    ):
        """Test the get_weather function with a number of higher data frequencies."""
        freq = "1H"
        clear_outside_api.freq_output = freq
        clear_outside_api.max_forecast_days = max_forecast_day
        weather = clear_outside_api.get_weather()
        assert isinstance(weather, dict)
        weather = self.convert_to_df(weather)
        assert isinstance(weather, DataFrame)
        assert infer_freq(weather.index) in time_aliases[freq]
        assert not weather.isna().values.any()
        n_rows = weather.shape[0]
        assert n_rows % (Timedelta(hours=24) / Timedelta(freq)) == 0
        assert n_rows <= max_forecast_day / Timedelta(freq)
        assert weather.index[0] == clear_outside_api.start_forecast
        assert weather.index[-1] == clear_outside_api.end_forecast - Timedelta(freq)

    def test_weather_data_cache(self, clear_outside_api: WeatherAPIClearOutside):
        """Test the get_weather function."""

        # get first weather data object
        weather1 = clear_outside_api.get_weather()
        assert isinstance(weather1, dict)
        weather1 = self.convert_to_df(weather1)
        assert isinstance(weather1, DataFrame)
        assert weather1.index[0] == clear_outside_api.start_forecast
        assert weather1.index[-1] == clear_outside_api.end_forecast - Timedelta("1h")
        last_update1 = clear_outside_api._last_update

        # get second weather data object, should see that it is cached data
        weather2 = clear_outside_api.get_weather()
        assert isinstance(weather2, dict)
        weather2 = self.convert_to_df(weather2)
        assert isinstance(weather2, DataFrame)
        last_update2 = clear_outside_api._last_update
        assert last_update1 == last_update2
        assert weather2.index[0] == clear_outside_api.start_forecast
        assert weather2.index[-1] == clear_outside_api.end_forecast - Timedelta("1h")

    def test_weather_data_live(self, clear_outside_api: WeatherAPIClearOutside):
        """Test the get_weather function."""

        # get first weather data object
        weather1 = clear_outside_api.get_weather()
        assert isinstance(weather1, dict)
        weather1 = self.convert_to_df(weather1)
        assert isinstance(weather1, DataFrame)
        assert weather1.index[0] == clear_outside_api.start_forecast
        assert weather1.index[-1] == clear_outside_api.end_forecast - Timedelta("1h")
        last_update1 = clear_outside_api._last_update

        # get second weather data object, should see that it is live data
        weather2 = clear_outside_api.get_weather(live=True)
        assert isinstance(weather2, dict)
        weather2 = self.convert_to_df(weather2)
        assert isinstance(weather2, DataFrame)
        assert weather2.index[0] == clear_outside_api.start_forecast
        assert weather2.index[-1] == clear_outside_api.end_forecast - Timedelta("1h")
        last_update2 = clear_outside_api._last_update
        assert last_update1 != last_update2
