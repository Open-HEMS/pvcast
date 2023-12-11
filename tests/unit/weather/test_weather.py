"""Test the weather module."""
from __future__ import annotations

import datetime as dt
from datetime import timezone as tz
from typing import Generator

import polars as pl
import pytest
import requests
import responses
from pvlib.location import Location

from pvcast.weather.weather import (
    WeatherAPI,
    WeatherAPIError,
    WeatherAPIErrorTooManyReq,
    WeatherAPIErrorWrongURL,
    WeatherAPIFactory,
)


# mock for WeatherAPI class
class MockWeatherAPI(WeatherAPI):
    """Mock the WeatherAPI class."""

    def __init__(self, location: Location, url: str, data: pl.DataFrame = None):
        """Initialize the mock class."""
        super().__init__(location, url, freq_source=dt.timedelta(minutes=30))
        self.url = url
        self.data = data

    def _process_data(self) -> pl.DataFrame:
        """Get weather data from API response."""
        if self.data is None:
            if self._raw_data is None:
                raise WeatherAPIError("No data available.")
            resp: requests.Response = self._raw_data
            data = pl.from_dict(resp.json())
        else:
            data = self.data

        # convert datetime column to datetime type
        data = data.with_columns(
            pl.col("datetime").str.to_datetime(format="%Y-%m-%dT%H:%M:%S%z")
        )
        return data


class TestWeather:
    """Test the weather module."""

    error_dict = {
        404: WeatherAPIErrorWrongURL,
        429: WeatherAPIErrorTooManyReq,
        500: WeatherAPIError,
    }

    test_url = "http://fakeurl.com/status/"

    # define test data
    mock_data = pl.DataFrame(
        {
            "temperature": [0, 0.5, 1],
            "humidity": [0, 0.5, 1],
            "wind_speed": [0, 0.5, 1],
            "cloud_coverage": [0, 0.5, 1],
            "datetime": [
                "2020-01-01T00:00:00+00:00",
                "2020-01-01T00:30:00+00:00",
                "2020-01-01T01:00:00+00:00",
            ],
        }
    )

    # test data with NaN values
    mock_data_NaN = pl.DataFrame(
        {
            "temperature": [None, 0.5, None],
            "humidity": [0, 0.5, 1],
            "wind_speed": [0, 0.5, 1],
            "cloud_coverage": [0, 0.5, 1],
            "datetime": [
                "2020-01-01T00:00:00+00:00",
                "2020-01-01T00:30:00+00:00",
                "2020-01-01T01:00:00+00:00",
            ],
        }
    )

    # mock data that will not pass the schema validation
    mock_data_invalid = pl.DataFrame(
        {
            "temperature": [0, 0.5, 1],
            "humidity": [0, 0.5, 1],
            "wind_speed": [0, 0.5, 1],
            "cloud_coverage": [0, 0.5, 1],
            "invalid_column": [0, 0.5, 1],
            "datetime": [
                "2020-01-01T00:00:00+00:00",
                "2020-01-01T00:30:00+00:00",
                "2020-01-01T01:00:00+00:00",
            ],
        }
    )

    @pytest.fixture
    def api_response(
        self, request: pytest.FixtureRequest
    ) -> Generator[requests.Response, None, None]:
        """Get a weather API response."""
        # if request is not parametrized, use a default response
        if not hasattr(request, "param"):
            data: pl.DataFrame = self.mock_data
        else:
            data = request.param

        data = data.to_dict(as_series=False)
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, self.test_url, json=data)
            response = requests.get(self.test_url)
            yield response

    @pytest.fixture
    def api_error_response(
        self, request: pytest.FixtureRequest
    ) -> Generator[requests.Response, None, None]:
        """Get a weather API error response."""
        error_code = int(request.param["error_code"])
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, self.test_url, status=error_code)
            response = requests.get(self.test_url)
            yield response

    @pytest.fixture
    def weather_obj(
        self, location: Location, api_response: requests.Response
    ) -> WeatherAPI:
        """Get a weather API object."""
        api = MockWeatherAPI(location=location, url=self.test_url)
        api._last_update = dt.datetime.now(tz.utc)
        api._raw_data = api_response
        return api

    @pytest.fixture
    def weather_obj_error(
        self, location: Location, api_error_response: requests.Response
    ) -> WeatherAPI:
        """Get a weather API object."""
        api = MockWeatherAPI(location=location, url=self.test_url)
        api._last_update = dt.datetime.now(tz.utc)
        api._raw_data = api_error_response
        return api

    @pytest.fixture
    def weather_obj_fixed_loc(self, api_response: requests.Response) -> WeatherAPI:
        """Get a weather API object."""
        api = MockWeatherAPI(
            url=self.test_url, location=Location(52.35818, 4.88124, tz="UTC")
        )
        api._last_update = dt.datetime.now(tz.utc)
        api._raw_data = api_response
        return api

    def test_weather_obj_init(self, weather_obj: WeatherAPI) -> None:
        """Test the get_weather function."""
        assert isinstance(weather_obj, WeatherAPI)
        assert isinstance(weather_obj.location, Location)

    def test_get_weather_no_update(self, weather_obj_fixed_loc: WeatherAPI) -> None:
        """Test the get_weather function."""
        weather_obj_fixed_loc.get_weather()
        assert weather_obj_fixed_loc.last_update is not None
        dt_now = dt.datetime.now(tz.utc)
        dt_delta = dt_now - weather_obj_fixed_loc.last_update
        assert dt_delta.total_seconds() < 1

    @pytest.mark.parametrize("api_response", [mock_data_NaN], indirect=True)
    def test_get_weather_NaN(self, weather_obj_fixed_loc: WeatherAPI) -> None:
        """Test the get_weather function when NaN values are present."""
        with pytest.raises(
            WeatherAPIError, match="Processed data contains NaN values."
        ):
            weather_obj_fixed_loc.get_weather()

    @pytest.mark.parametrize("api_response", [mock_data_invalid], indirect=True)
    def test_get_weather_schema_error(self, weather_obj_fixed_loc: WeatherAPI) -> None:
        """Test the get_weather function when NaN values are present."""
        with pytest.raises(WeatherAPIError, match="Error validating weather data:"):
            weather_obj_fixed_loc.get_weather()

    @pytest.mark.parametrize(
        "api_error_response",
        [
            {"error_code": code, "data": data}
            for (code, data) in zip(error_dict.keys(), [mock_data] * len(error_dict))
        ],
        indirect=True,
    )
    def test_http_error_handling(self, weather_obj_error: WeatherAPI) -> None:
        """Test the get_weather error handling function."""
        if weather_obj_error._raw_data is None:
            raise ValueError("No data available.")
        error_code = weather_obj_error._raw_data.status_code
        with pytest.raises(self.error_dict[error_code]):
            weather_obj_error.get_weather()

    @pytest.mark.parametrize(
        "irradiance_method", ["campbell_norman", "clearsky_scaling"]
    )
    def test_weather_cloud_cover_to_irradiance(
        self, weather_obj: WeatherAPI, weather_df: pl.DataFrame, irradiance_method: str
    ) -> None:
        """Test the cloud_cover_to_irradiance function."""
        irradiance = weather_obj.cloud_cover_to_irradiance(
            weather_df["cloud_cover"], irradiance_method
        )
        rad_types = {"ghi", "dni", "dhi"}
        assert isinstance(irradiance, pl.DataFrame)
        assert irradiance.shape[0] == weather_df.shape[0]
        assert irradiance.shape[1] == 3
        assert set(irradiance.columns) == rad_types
        for rad_type in rad_types:
            assert irradiance[rad_type].dtype == pl.Float64
            assert irradiance[rad_type].is_finite().all()
            assert irradiance[rad_type].min() >= 0
            assert irradiance[rad_type].max() <= 1367

    def test_weather_cloud_cover_to_irradiance_error(
        self, weather_obj: WeatherAPI, weather_df: pl.DataFrame
    ) -> None:
        """Test the cloud_cover_to_irradiance function with errors."""
        with pytest.raises(ValueError):
            weather_obj.cloud_cover_to_irradiance(
                weather_df["cloud_cover"], "wrong_method"
            )
        with pytest.raises(ValueError):
            weather_obj.cloud_cover_to_irradiance(
                weather_df["cloud_cover"], method="wrong_method"
            )


class TestWeatherFactory:
    """Test the weather factory module."""

    test_url = "http://fakeurl.com/status/"

    @pytest.fixture
    def weather_api_factory(self) -> WeatherAPIFactory:
        """Get a weather API factory."""
        API_FACTORY_TEST = WeatherAPIFactory()
        API_FACTORY_TEST.register("mock", MockWeatherAPI)
        return API_FACTORY_TEST

    def test_get_weather_api(self, weather_api_factory: WeatherAPIFactory) -> None:
        """Test the get_weather_api function."""
        assert isinstance(weather_api_factory, WeatherAPIFactory)
        assert isinstance(
            weather_api_factory.get_weather_api(
                "mock", location=Location(0, 0, "UTC", 0), url=self.test_url
            ),
            MockWeatherAPI,
        )
        with pytest.raises(ValueError):
            weather_api_factory.get_weather_api(
                "wrong_api", location=Location(0, 0, "UTC", 0), url=self.test_url
            )

    def test_get_weather_api_list_obj(
        self, weather_api_factory: WeatherAPIFactory
    ) -> None:
        """Test the get_weather_api function with a list of objects."""
        assert isinstance(weather_api_factory, WeatherAPIFactory)
        api_list = weather_api_factory.get_weather_api_list_obj()
        assert isinstance(api_list, list)
        assert len(api_list) == 1

    def test_get_weather_api_list_str(
        self, weather_api_factory: WeatherAPIFactory
    ) -> None:
        """Test the get_weather_api function with a list of strings."""
        assert isinstance(weather_api_factory, WeatherAPIFactory)
        api_list = weather_api_factory.get_weather_api_list_str()
        assert isinstance(api_list, list)
        assert len(api_list) == 1
        assert api_list[0] == "mock"
