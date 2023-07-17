"""Test all configured weather platforms that inherit from WeatherAPI class."""
from __future__ import annotations

import json

import pytest
import requests
import responses
from const import HASS_TEST_TOKEN, HASS_TEST_URL, LOC_EUW, LOC_USW
from pandas import DataFrame, Timedelta, infer_freq, to_datetime
from pvlib.location import Location

from pvcast.weather import API_FACTORY
from pvcast.weather.hass import WeatherAPIHASS
from pvcast.weather.weather import WeatherAPI


class TestWeatherPlatform:
    """Test a weather platform that inherits from WeatherAPI class."""

    weatherapis = API_FACTORY.get_weather_api_list_obj()
    valid_temp_units = ["°C", "°F", "C", "F"]
    valid_speed_units = ["m/s", "km/h", "mi/h", "ft/s", "kn"]

    @pytest.fixture
    def weather_test_data(self):
        """Load the weather test data."""
        with open("tests/test_weather_data.json") as json_file:
            weather_data = json.load(json_file)
            # set to 1 to easily test if the data is correctly converted
            for forecast in weather_data["attributes"]["forecast"]:
                forecast["wind_speed"] = 1.0
                forecast["temperature"] = 1.0
            return weather_data

    @pytest.fixture
    def temperature_unit(self, weather_test_data, request):
        """Load the weather test data."""
        weather_test_data["attributes"]["temperature_unit"] = request.param
        return weather_test_data

    @pytest.fixture
    def wind_speed_unit(self, temperature_unit, request):
        """Load the weather test data."""
        temperature_unit["attributes"]["wind_speed_unit"] = request.param
        return temperature_unit

    @pytest.fixture()
    def time_aliases(self, pd_time_aliases):
        return pd_time_aliases

    @pytest.fixture(params=[LOC_EUW, LOC_USW])
    def location(self, request):
        """Fixture that creates a location."""
        return Location(*request.param)

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
        return Timedelta(days=request.param)

    def convert_to_df(self, weather):
        """Convert the weather data to a DataFrame."""
        weather = DataFrame.from_dict(weather["data"])
        weather.set_index("datetime", inplace=True)
        weather.index = to_datetime(weather.index)
        return weather

    def test_weather_get_weather(self, weatherapi: WeatherAPI):
        """Test the get_weather function."""
        weather = weatherapi.get_weather()
        assert isinstance(weather, dict)
        weather = self.convert_to_df(weather)
        assert isinstance(weather, DataFrame)
        # assert infer_freq(weather.index) == "H"
        assert not weather.isna().values.any()
        assert weather.shape[0] >= 24

    @pytest.mark.parametrize("freq", ["1H", "30Min", "15Min"])
    def test_weather_get_weather_freq(self, weatherapi: WeatherAPI, freq, time_aliases):
        """Test the get_weather function with a number of higher data frequencies."""
        weatherapi.freq_output = freq
        weather = weatherapi.get_weather()
        assert isinstance(weather, dict)
        weather = self.convert_to_df(weather)
        assert isinstance(weather, DataFrame)
        assert infer_freq(weather.index) in time_aliases[freq]
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
        assert isinstance(weather, DataFrame)
        assert infer_freq(weather.index) in time_aliases[freq]
        assert not weather.isna().values.any()
        assert weather.shape[0] >= 24
        assert weather.shape[0] <= max_forecast_day / Timedelta(freq)

    def test_weather_data_cache(self, weatherapi: WeatherAPI):
        """Test the get_weather function."""
        # get first weather data object
        weather1 = weatherapi.get_weather()
        assert isinstance(weather1, dict)
        weather1 = self.convert_to_df(weather1)
        assert isinstance(weather1, DataFrame)
        last_update1 = weatherapi._last_update

        # get second weather data object, should see that it is cached data
        weather2 = weatherapi.get_weather()
        assert isinstance(weather2, dict)
        weather2 = self.convert_to_df(weather2)
        assert isinstance(weather2, DataFrame)
        last_update2 = weatherapi._last_update
        assert last_update1 == last_update2

    def test_weather_data_live(self, weatherapi: WeatherAPI):
        """Test the get_weather function."""

        # get first weather data object
        weather1 = weatherapi.get_weather()
        assert isinstance(weather1, dict)
        weather1 = self.convert_to_df(weather1)
        assert isinstance(weather1, DataFrame)
        last_update1 = weatherapi._last_update

        # get second weather data object, should see that it is live data
        weather2 = weatherapi.get_weather(live=True)
        assert isinstance(weather2, dict)
        weather2 = self.convert_to_df(weather2)
        assert isinstance(weather2, DataFrame)
        last_update2 = weatherapi._last_update
        assert last_update1 != last_update2


class TestWeatherPlatformHASS(TestWeatherPlatform):
    """A few extra tests for the HASS weather platform specific functionality."""

    @pytest.fixture
    def weather_response(self, wind_speed_unit):
        """Mock a weather API response."""
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, "http://localhost:8123/api/", json=wind_speed_unit, status=200)
            yield rsps

    @pytest.fixture()
    def weatherapi(self, location):
        """Fixture that creates a weather API interface."""
        return WeatherAPIHASS(
            entity_id="weather.forecast_thuis_hourly",
            url=HASS_TEST_URL,
            token=HASS_TEST_TOKEN,
            location=location,
        )

    def test_hass_init_errors(self):
        """Init WeatherAPIHASS with wrong parameters."""
        with pytest.raises(ValueError) as exc:
            WeatherAPIHASS(
                entity_id="weather.forecast_thuis_hourly",
                url=HASS_TEST_URL,
                token=None,
                location=None,
            )
            assert "Token not set." in str(exc)
        with pytest.raises(ValueError):
            WeatherAPIHASS(
                entity_id=None,
                url=HASS_TEST_URL,
                token=None,
                location=None,
            )
            assert "Entity ID not set." in str(exc)

    @pytest.mark.parametrize("temperature_unit", ["°C", "°F", "C", "F"] + ["wrong"], indirect=True)
    @pytest.mark.parametrize("wind_speed_unit", ["m/s", "km/h", "mi/h", "ft/s", "kn"] + ["wrong"], indirect=True)
    def test_hass_process_data(self, weather_response, temperature_unit, wind_speed_unit):
        """Test the process_data function."""
        weatherapi = WeatherAPIHASS(
            entity_id="n/a",
            url=HASS_TEST_URL,
            token=HASS_TEST_TOKEN,
            location=Location(0, 0),
        )

        # set raw data
        resp = requests.get("http://localhost:8123/api/")
        weatherapi._raw_data = resp
        temp_unit = weatherapi._raw_data.json()["attributes"]["temperature_unit"]
        wind_unit = weatherapi._raw_data.json()["attributes"]["wind_speed_unit"]

        # test the _process_data function
        if temp_unit not in self.valid_temp_units or wind_unit not in self.valid_speed_units:
            with pytest.raises(ValueError):
                weatherapi._process_data()
        else:
            weather_df = weatherapi._process_data()
            assert isinstance(weather_df, DataFrame)
            assert not weather_df.isna().values.any()
