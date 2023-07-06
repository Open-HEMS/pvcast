"""Test the weather module."""
from __future__ import annotations

from unittest import mock

import pytest
import requests
from const import LOC_AUS, LOC_EUW, LOC_USW
from pandas import DataFrame
from pvlib.location import Location

from pvcast.weather.weather import (WeatherAPI, WeatherAPIError,
                                    WeatherAPIErrorTooManyReq,
                                    WeatherAPIErrorWrongURL)


# mock for WeatherAPI class
class MockWeatherAPI(WeatherAPI):
    """Mock the WeatherAPI class."""

    def _process_data(self, response: requests.Response) -> DataFrame:
        """Get weather data from API response."""
        return DataFrame()


class TestWeather:
    """Test the weather module."""

    @pytest.fixture(params=[LOC_EUW, LOC_USW, LOC_AUS])
    def weather_obj(self, request):
        """Get a weather API object."""
        return MockWeatherAPI(location=Location(*request.param), url="http://httpbin.org/get")

    @pytest.fixture(params=[404, 429, 500])
    def weather_obj_error(self, request):
        """Get a weather API object with an error."""

        url_base = "http://httpbin.org/status/"
        url = f"{url_base}{request.param}"
        obj = MockWeatherAPI(location=Location(0, 0, "UTC", 0), url=url)
        return obj

    @pytest.fixture(params=["campbell_norman", "clearsky_scaling"])
    def irradiance_method(self, request):
        """Get irradiance methods."""
        return request.param

    def test_get_weather_obj(self, weather_obj):
        """Test the get_weather function."""
        assert isinstance(weather_obj, WeatherAPI)
        assert isinstance(weather_obj.location, Location)

    def test_error_handling(self, weather_obj_error):
        """Test the get_weather error handling function."""
        error_dict = {
            404: WeatherAPIErrorWrongURL,
            429: WeatherAPIErrorTooManyReq,
            500: WeatherAPIError,
        }
        code = int(weather_obj_error.url.split("/")[-1])
        with pytest.raises(error_dict[code]):
            weather_obj_error._api_request_if_needed()

    def test_weather_cloud_cover_to_irradiance(
        self, weather_obj: WeatherAPI, weather_df: DataFrame, irradiance_method: str
    ):
        """Test the cloud_cover_to_irradiance function."""
        irradiance = weather_obj.cloud_cover_to_irradiance(weather_df["cloud_cover"], irradiance_method)
        assert isinstance(irradiance, DataFrame)
        assert irradiance.shape[0] == weather_df.shape[0]
        assert irradiance.shape[1] == 3
        assert set(irradiance.columns) == {"ghi", "dni", "dhi"}
        assert irradiance.index.equals(weather_df.index)
