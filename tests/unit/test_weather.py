"""Test the weather module."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import requests
import responses
from pvlib.location import Location

from pvcast.weather.weather import (WeatherAPI, WeatherAPIError,
                                    WeatherAPIErrorTooManyReq,
                                    WeatherAPIErrorWrongURL, WeatherAPIFactory)


# mock for WeatherAPI class
class MockWeatherAPI(WeatherAPI):
    """Mock the WeatherAPI class."""

    def __init__(self, location: Location, url: str):
        """Initialize the mock class."""
        super().__init__(location, url, freq_source="30T")
        self.url = url

    def _process_data(self) -> pd.DataFrame:
        """Get weather data from API response."""
        index = pd.DatetimeIndex(
            ["2020-01-01 00:00:00", "2020-01-01 00:30:00", "2020-01-01 01:00:00"], tz="UTC", freq="30T"
        )
        # add temperature, humidity, wind_speed, cloud_coverage
        data = [
            [0, 0, 0, 0],
            [0.5, 0.5, 0.5, 0.5],
            [1, 1, 1, 1],
        ]
        columns = ["temperature", "humidity", "wind_speed", "cloud_coverage"]
        return pd.DataFrame(data, index=index, columns=columns)


class TestWeather:
    """Test the weather module."""

    error_dict = {
        404: WeatherAPIErrorWrongURL,
        429: WeatherAPIErrorTooManyReq,
        500: WeatherAPIError,
    }

    # Define test data
    unit_conv_data = pd.Series(
        [-10.0, 0.0, 25.0, 100.0, 37.0], name="temperature", index=[0, 1, 2, 3, 4], dtype=np.float64
    )

    # fahrenheit to celsius conversion
    f_to_c_out = pd.Series(
        [-23.3333, -17.7778, -3.8889, 37.7778, 2.7778],
        name="temperature",
        index=[0, 1, 2, 3, 4],
        dtype=np.float64,
    )

    # define valid test cases for temperature conversion
    # fmt: off
    valid_temperature_test_cases = [
        ("°F", "°C", f_to_c_out),
        ("°F", "C", f_to_c_out),
        ("F", "°C", f_to_c_out),
        ("F", "C", f_to_c_out),
        ("C", "C", unit_conv_data),
    ]
    # fmt: on

    # define invalid test cases for temperature conversion
    invalid_temperature_test_cases = [
        ("C", "invalid_unit"),
        ("invalid_unit", "C"),
        ("invalid_unit", "invalid_unit"),
        ("invalid_unit", "F"),
    ]

    # define valid test cases for speed conversion
    # fmt: off
    valid_speed_test_cases = [
        ("m/s", "km/h", pd.Series([-36.0, 0.0, 90.0, 360.0, 133.2], index=[0, 1, 2, 3, 4], dtype=np.float64)),
        ("km/h", "m/s", pd.Series([-2.78, 0.0, 6.94, 27.78, 10.28], index=[0, 1, 2, 3, 4], dtype=np.float64)),
        ("mi/h", "m/s", pd.Series([-4.47, 0.0, 11.18, 44.70, 16.54], index=[0, 1, 2, 3, 4], dtype=np.float64)),
    ]
    # fmt: on

    # define invalid test cases for speed conversion
    invalid_speed_test_cases = [
        ("m/s", "invalid_unit"),
        ("invalid_unit", "km/h"),
        ("invalid_unit", "invalid_unit"),
        ("invalid_unit", "mi/h"),
    ]

    test_url = "http://fakeurl.com/status/"

    @pytest.fixture
    def api_response(self, ha_weather_data):
        """Get a weather API response."""
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, self.test_url, json=ha_weather_data)
            response = requests.get(self.test_url)
            yield response

    @pytest.fixture
    def api_error_response(self, request: int):
        """Get a weather API error response."""
        error_code = request.param
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, self.test_url, status=error_code)
            response = requests.get(self.test_url)
            yield response

    @pytest.fixture
    def weather_obj(self, location, api_response):
        """Get a weather API object."""
        api = MockWeatherAPI(location=location, url=self.test_url)
        api._last_update = pd.Timestamp.now(tz="UTC")
        api._raw_data = api_response
        return api

    @pytest.fixture
    def weather_obj_fixed_loc(self, api_response):
        """Get a weather API object."""
        api = MockWeatherAPI(url=self.test_url, location=Location(52.35818, 4.88124, tz="UTC"))
        api._last_update = pd.Timestamp.now(tz="UTC")
        api._raw_data = api_response
        return api

    @pytest.fixture(params=["campbell_norman", "clearsky_scaling"])
    def irradiance_method(self, request):
        """Get irradiance methods."""
        return request.param

    def test_weather_obj_init(self, weather_obj):
        """Test the get_weather function."""
        assert isinstance(weather_obj, WeatherAPI)
        assert isinstance(weather_obj.location, Location)

    def test_get_weather_no_update(self, weather_obj_fixed_loc):
        """Test the get_weather function."""
        weather_obj_fixed_loc.get_weather()
        assert pd.Timestamp.now(tz="UTC") - weather_obj_fixed_loc._last_update < pd.Timedelta(seconds=1)

    @pytest.mark.parametrize("api_error_response", [404, 429, 500], indirect=True)
    def test_http_error_handling(self, api_error_response: responses.Response, weather_obj: WeatherAPI):
        """Test the get_weather error handling function."""
        weather_obj._raw_data = api_error_response
        error_code = api_error_response.status_code
        with pytest.raises(self.error_dict[error_code]):
            weather_obj.get_weather()

    def test_weather_cloud_cover_to_irradiance(
        self, weather_obj: WeatherAPI, weather_df: pd.DataFrame, irradiance_method: str
    ):
        """Test the cloud_cover_to_irradiance function."""
        irradiance = weather_obj.cloud_cover_to_irradiance(weather_df["cloud_cover"], irradiance_method)
        assert isinstance(irradiance, pd.DataFrame)
        assert irradiance.shape[0] == weather_df.shape[0]
        assert irradiance.shape[1] == 3
        assert set(irradiance.columns) == {"ghi", "dni", "dhi"}
        assert irradiance.index.equals(weather_df.index)

    def test_weather_cloud_cover_to_irradiance_error(self, weather_obj: WeatherAPI, weather_df: pd.DataFrame):
        """Test the cloud_cover_to_irradiance function with errors."""
        with pytest.raises(ValueError):
            weather_obj.cloud_cover_to_irradiance(weather_df["cloud_cover"], "wrong_method")
        with pytest.raises(ValueError):
            weather_obj.cloud_cover_to_irradiance(weather_df["cloud_cover"], method="wrong_method")

    @pytest.mark.parametrize("freq_opt, freq", [(None, "30T"), ("30T", None), ("30T", "30T")])
    def test_add_freq(self, weather_obj: WeatherAPI, freq_opt: str | None, freq: str | None):
        """Test the add_freq function."""
        index = pd.DatetimeIndex(
            ["2020-01-01 00:00:00", "2020-01-01 00:30:00", "2020-01-01 01:00:00"], tz="UTC", freq=freq_opt
        )
        if freq_opt is None:
            assert index.freq is None
        else:
            assert index.freq.freqstr == freq_opt
        weather_df = weather_obj._add_freq(index, freq)
        assert weather_df.freq == "30T"

    @pytest.mark.parametrize("from_unit, to_unit, expected", valid_temperature_test_cases + valid_speed_test_cases)
    def test_valid_conversion(self, weather_obj_fixed_loc: WeatherAPI, from_unit, to_unit, expected):
        result = weather_obj_fixed_loc.convert_unit(self.unit_conv_data, from_unit, to_unit)
        pd.testing.assert_series_equal(
            result, expected, check_dtype=False, atol=0.01, check_exact=False, check_names=False
        )

    @pytest.mark.parametrize("from_unit, to_unit", invalid_temperature_test_cases + invalid_speed_test_cases)
    def test_invalid_conversion(self, weather_obj_fixed_loc: WeatherAPI, from_unit, to_unit):
        with pytest.raises(ValueError):
            weather_obj_fixed_loc.convert_unit(self.unit_conv_data, from_unit, to_unit)

    def test_invalid_data_type(self, weather_obj_fixed_loc: WeatherAPI):
        with pytest.raises(TypeError):
            weather_obj_fixed_loc.convert_unit([0, 25, 100, 37], "C", "F")


class TestWeatherFactory:
    """Test the weather factory module."""

    test_url = "http://fakeurl.com/status/"

    @pytest.fixture
    def weather_api_factory(self):
        """Get a weather API factory."""
        API_FACTORY_TEST = WeatherAPIFactory()
        API_FACTORY_TEST.register("mock", MockWeatherAPI)
        return API_FACTORY_TEST

    def test_get_weather_api(self, weather_api_factory):
        """Test the get_weather_api function."""
        assert isinstance(weather_api_factory, WeatherAPIFactory)
        assert isinstance(
            weather_api_factory.get_weather_api("mock", location=Location(0, 0, "UTC", 0), url=self.test_url),
            MockWeatherAPI,
        )
        with pytest.raises(ValueError):
            weather_api_factory.get_weather_api("wrong_api", location=Location(0, 0, "UTC", 0), url=self.test_url)

    def test_get_weather_api_list_obj(self, weather_api_factory):
        """Test the get_weather_api function with a list of objects."""
        assert isinstance(weather_api_factory, WeatherAPIFactory)
        api_list = weather_api_factory.get_weather_api_list_obj()
        assert isinstance(api_list, list)
        assert len(api_list) == 1
        assert issubclass(api_list[0], MockWeatherAPI)

    def test_get_weather_api_list_str(self, weather_api_factory):
        """Test the get_weather_api function with a list of strings."""
        assert isinstance(weather_api_factory, WeatherAPIFactory)
        api_list = weather_api_factory.get_weather_api_list_str()
        assert isinstance(api_list, list)
        assert len(api_list) == 1
        assert api_list[0] == "mock"
