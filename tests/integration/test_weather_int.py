"""Test all configured weather platforms that inherit from WeatherAPI class."""
from __future__ import annotations

import pandas as pd
import pytest
from const import HASS_TEST_TOKEN, HASS_TEST_URL

from pvcast.weather import API_FACTORY
from pvcast.weather.hass import WeatherAPIHASS
from pvcast.weather.weather import WeatherAPI


class TestWeatherPlatform:
    """Test a weather platform that inherits from WeatherAPI class."""

    weatherapis = API_FACTORY.get_weather_api_list_obj()
    valid_temp_units = ["°C", "°F", "C", "F"]
    valid_speed_units = ["m/s", "km/h", "mi/h", "ft/s", "kn"]

    @pytest.fixture()
    def time_aliases(self, pd_time_aliases):
        return pd_time_aliases

    @pytest.fixture(params=weatherapis)
    def weatherapi(self, request, location):
        """Fixture that creates a weather API interface."""
        if request.param == WeatherAPIHASS:
            return WeatherAPIHASS(
                entity_id="weather.forecast_thuis_hourly",
                url=HASS_TEST_URL,
                token=HASS_TEST_TOKEN,
                location=location,
            )
        return request.param(location=location)

    @pytest.fixture(params=[1, 2, 3])
    def max_forecast_day(self, request):
        return pd.TimeDelta(days=request.param)

    def convert_to_df(self, weather):
        """Convert the weather data to a pd.DataFrame."""
        weather = pd.DataFrame.from_dict(weather["data"])
        weather.set_index("datetime", inplace=True)
        weather.index = pd.to_datetime(weather.index)
        return weather

    def test_weather_get_weather(self, weatherapi: WeatherAPI):
        """Test the get_weather function."""
        weather = weatherapi.get_weather()
        assert isinstance(weather, dict)
        weather = self.convert_to_df(weather)
        assert isinstance(weather, pd.DataFrame)
        # assert pd.infer_freq(weather.index) == "H"
        assert not weather.isna().values.any()
        assert weather.shape[0] >= 24

    @pytest.mark.parametrize("freq", ["1H", "30Min", "15Min"])
    def test_weather_get_weather_freq(self, weatherapi: WeatherAPI, freq, time_aliases):
        """Test the get_weather function with a number of higher data frequencies."""
        weatherapi.freq_output = freq
        weather = weatherapi.get_weather()
        assert isinstance(weather, dict)
        weather = self.convert_to_df(weather)
        assert isinstance(weather, pd.DataFrame)
        assert pd.infer_freq(weather.index) in time_aliases[freq]
        assert not weather.isna().values.any()
        assert weather.shape[0] >= 24

    def test_weather_get_weather_max_days(self, weatherapi: WeatherAPI, max_forecast_day, time_aliases):
        """Test the get_weather function with a number of higher data frequencies."""
        freq = "1H"
        weatherapi.freq_output = freq
        weatherapi.max_forecast_days = max_forecast_day
        weather = weatherapi.get_weather()
        assert isinstance(weather, dict)
        weather = self.convert_to_df(weather)
        assert isinstance(weather, pd.DataFrame)
        assert pd.infer_freq(weather.index) in time_aliases[freq]
        assert not weather.isna().values.any()
        assert weather.shape[0] >= 24
        assert weather.shape[0] <= max_forecast_day / pd.TimeDelta(freq)

    def test_weather_data_cache(self, weatherapi: WeatherAPI):
        """Test the get_weather function."""
        # get first weather data object
        weather1 = weatherapi.get_weather()
        assert isinstance(weather1, dict)
        weather1 = self.convert_to_df(weather1)
        assert isinstance(weather1, pd.DataFrame)
        last_update1 = weatherapi._last_update

        # get second weather data object, should see that it is cached data
        weather2 = weatherapi.get_weather()
        assert isinstance(weather2, dict)
        weather2 = self.convert_to_df(weather2)
        assert isinstance(weather2, pd.DataFrame)
        last_update2 = weatherapi._last_update
        assert last_update1 == last_update2

    def test_weather_data_live(self, weatherapi: WeatherAPI):
        """Test the get_weather function."""

        # get first weather data object
        weather1 = weatherapi.get_weather()
        assert isinstance(weather1, dict)
        weather1 = self.convert_to_df(weather1)
        assert isinstance(weather1, pd.DataFrame)
        last_update1 = weatherapi._last_update

        # get second weather data object, should see that it is live data
        weather2 = weatherapi.get_weather(live=True)
        assert isinstance(weather2, dict)
        weather2 = self.convert_to_df(weather2)
        assert isinstance(weather2, pd.DataFrame)
        last_update2 = weatherapi._last_update
        assert last_update1 != last_update2
