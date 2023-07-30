"""Test the weather module."""
from __future__ import annotations

import pandas as pd
import pytest
import requests
import responses
from const import LOC_AUS, LOC_EUW, LOC_USW
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
        index = pd.DatetimeIndex(["2020-01-01 00:00:00", "2020-01-01 00:30:00", "2020-01-01 01:00:00"], tz="UTC")
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

    @pytest.fixture(params=[LOC_EUW, LOC_USW, LOC_AUS])
    def weather_obj(self, request):
        """Get a weather API object."""
        return MockWeatherAPI(location=Location(*request.param), url="http://fakeurl.com/status/")

    @pytest.fixture
    def api_error_response(self, request: int):
        """Get a weather API error response."""
        url = "http://fakeurl.com/status/"
        error_code = request.param
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, url, status=error_code)
            response = requests.get(url)
            yield response

    @pytest.fixture(params=["campbell_norman", "clearsky_scaling"])
    def irradiance_method(self, request):
        """Get irradiance methods."""
        return request.param

    def test_get_weather_obj(self, weather_obj):
        """Test the get_weather function."""
        assert isinstance(weather_obj, WeatherAPI)
        assert isinstance(weather_obj.location, Location)

    @pytest.mark.parametrize("api_error_response", [404, 429, 500], indirect=True)
    def test_error_handling(self, api_error_response: responses.Response, weather_obj: WeatherAPI):
        """Test the get_weather error handling function."""
        weather_obj._raw_data = api_error_response
        weather_obj._last_update = pd.Timestamp.now(tz="UTC")
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


class TestWeatherFactory:
    """Test the weather factory module."""

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
            weather_api_factory.get_weather_api(
                "mock", location=Location(0, 0, "UTC", 0), url="http://notarealurl.com"
            ),
            MockWeatherAPI,
        )
        with pytest.raises(ValueError):
            weather_api_factory.get_weather_api(
                "wrong_api", location=Location(0, 0, "UTC", 0), url="http://notarealurl.com"
            )

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