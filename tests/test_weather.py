"""Test the weather module."""
from __future__ import annotations

import pytest
import requests
from const import LOC_AUS, LOC_EUW, LOC_USW
from pandas import DataFrame

from pvcast.weather.weather import (
    WeatherAPI,
    WeatherAPIError,
    WeatherAPIErrorNoData,
    WeatherAPIErrorTimeout,
    WeatherAPIErrorTooManyReq,
    WeatherAPIErrorWrongURL,
)


class TestWeather:
    """Test the weather module."""

    @pytest.fixture(params=[LOC_EUW, LOC_USW, LOC_AUS])
    def weather_obj(self, request):
        """Get a weather API object."""

        class WeatherAPITest(WeatherAPI):
            """Weather API test object."""

            def _process_data(self, response: requests.Response) -> DataFrame:
                """Get weather data from API response."""
                return DataFrame()

            def _url_formatter(self) -> str:
                """Format the url with lat, lon, alt."""
                return self._url

        return WeatherAPITest(*request.param, format_url=False)

    @pytest.fixture(params=[404, 429, 500])
    def weather_obj_error(self, request):
        """Get a weather API object with an error."""

        class WeatherAPITest(WeatherAPI):
            """Weather API test object."""

            _url_base = "http://httpbin.org/status/"
            code = request.param

            def _process_data(self, response: requests.Response) -> DataFrame:
                """Get weather data from API response."""
                return DataFrame()

            def _url_formatter(self) -> str:
                """Format the url with lat, lon, alt."""
                return f"{self._url_base}{request.param}"

        return WeatherAPITest(*LOC_EUW, format_url=True)

    def test_get_weather_obj(self, weather_obj):
        """Test the get_weather function."""
        assert isinstance(weather_obj, WeatherAPI)

    def test_error_handling(self, weather_obj_error):
        """Test the get_weather error handling function."""
        error_dict = {
            404: WeatherAPIErrorWrongURL,
            429: WeatherAPIErrorTooManyReq,
            500: WeatherAPIError,
        }
        with pytest.raises(error_dict[weather_obj_error.code]):
            weather_obj_error._api_request_if_needed()
