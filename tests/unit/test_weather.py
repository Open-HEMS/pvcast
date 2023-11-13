"""Test the weather module."""
from __future__ import annotations

from typing import Generator

import numpy as np
import pandas as pd
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

    def __init__(self, location: Location, url: str, data: pd.DataFrame = None):
        """Initialize the mock class."""
        super().__init__(location, url, freq_source="30T")
        self.url = url
        self.data = data

    def _process_data(self) -> pd.DataFrame:
        """Get weather data from API response."""
        if self.data is None:
            if self._raw_data is None:
                raise WeatherAPIError("No data available.")
            resp: requests.Response = self._raw_data
            data = pd.DataFrame.from_dict(resp.json(), orient="index")

            # convert index to DateTimeIndex
            data.index = pd.to_datetime(data.index, utc=True)
            data.index.freq = self.freq_source
        else:
            data = self.data
        return data


class TestWeather:
    """Test the weather module."""

    error_dict = {
        404: WeatherAPIErrorWrongURL,
        429: WeatherAPIErrorTooManyReq,
        500: WeatherAPIError,
    }

    # Define test data
    unit_conv_data = pd.Series(
        [-10.0, 0.0, 25.0, 100.0, 37.0],
        name="temperature",
        index=[0, 1, 2, 3, 4],
        dtype=np.float64,
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

    # define test data
    mock_data = pd.DataFrame(
        {
            "temperature": [0, 0.5, 1],
            "humidity": [0, 0.5, 1],
            "wind_speed": [0, 0.5, 1],
            "cloud_coverage": [0, 0.5, 1],
        },
        index=["2020-01-01 00:00:00", "2020-01-01 00:30:00", "2020-01-01 01:00:00"],
    )

    # test data with NaN values
    mock_data_NaN = pd.DataFrame(
        {
            "temperature": [pd.NA, 0.5, pd.NA],
            "humidity": [0, 0.5, 1],
            "wind_speed": [0, 0.5, 1],
            "cloud_coverage": [0, 0.5, 1],
        },
        index=["2020-01-01 00:00:00", "2020-01-01 00:30:00", "2020-01-01 01:00:00"],
    )

    # mock data that will not pass the schema validation
    mock_data_invalid = pd.DataFrame(
        {
            "temperature": [0, 0.5, 1],
            "humidity": [0, 0.5, 1],
            "wind_speed": [0, 0.5, 1],
            "cloud_coverage": [0, 0.5, 1],
            "invalid_column": [0, 0.5, 1],
        },
        index=["2020-01-01 00:00:00", "2020-01-01 00:30:00", "2020-01-01 01:00:00"],
    )

    @pytest.fixture
    def api_response(
        self, request: pytest.FixtureRequest
    ) -> Generator[requests.Response, None, None]:
        """Get a weather API response."""
        # if request is not parametrized, use a default response
        if not hasattr(request, "param"):
            data: pd.DataFrame = self.mock_data
        else:
            data = request.param

        data = data.to_dict(orient="index")
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
        api._last_update = pd.Timestamp.now(tz="UTC")
        api._raw_data = api_response
        return api

    @pytest.fixture
    def weather_obj_error(
        self, location: Location, api_error_response: requests.Response
    ) -> WeatherAPI:
        """Get a weather API object."""
        api = MockWeatherAPI(location=location, url=self.test_url)
        api._last_update = pd.Timestamp.now(tz="UTC")
        api._raw_data = api_error_response
        return api

    @pytest.fixture
    def weather_obj_fixed_loc(self, api_response: requests.Response) -> WeatherAPI:
        """Get a weather API object."""
        api = MockWeatherAPI(
            url=self.test_url, location=Location(52.35818, 4.88124, tz="UTC")
        )
        api._last_update = pd.Timestamp.now(tz="UTC")
        api._raw_data = api_response
        return api

    def test_weather_obj_init(self, weather_obj: WeatherAPI) -> None:
        """Test the get_weather function."""
        assert isinstance(weather_obj, WeatherAPI)
        assert isinstance(weather_obj.location, Location)

    def test_get_weather_no_update(self, weather_obj_fixed_loc: WeatherAPI) -> None:
        """Test the get_weather function."""
        weather_obj_fixed_loc.get_weather()
        assert pd.Timestamp.now(
            tz="UTC"
        ) - weather_obj_fixed_loc._last_update < pd.Timedelta(seconds=1)

    @pytest.mark.parametrize("api_response", [mock_data_NaN], indirect=True)
    def test_get_weather_NaN(self, weather_obj_fixed_loc: WeatherAPI) -> None:
        """Test the get_weather function when NaN values are present."""
        with pytest.raises(
            WeatherAPIError, match="Processed data contains NaN values."
        ):
            weather_obj_fixed_loc.get_weather()

    def test_get_weather_unknown_freq(self, api_response: requests.Response) -> None:
        """Test the get_weather function when the frequency is unknown."""
        api = MockWeatherAPI(
            url=self.test_url, location=Location(52.35818, 4.88124, tz="UTC")
        )
        api._last_update = pd.Timestamp.now(tz="UTC")
        api.data = self.mock_data.copy()
        # this should raise an error because the frequency cannot be inferred (dt = 30 min --> 15 min)
        api.data.index = pd.DatetimeIndex(
            ["2020-01-01 00:00:00", "2020-01-01 00:30:00", "2020-01-01 00:45:00"]
        )
        with pytest.raises(
            WeatherAPIError, match="Processed data does not have a known frequency."
        ):
            api.get_weather()

    def test_get_weather_conflicting_freq(
        self, api_response: requests.Response
    ) -> None:
        """Test the get_weather function when the frequency is unknown."""
        api = MockWeatherAPI(
            url=self.test_url, location=Location(52.35818, 4.88124, tz="UTC")
        )
        api._last_update = pd.Timestamp.now(tz="UTC")
        api.data = self.mock_data.copy()
        # self.freq_source = 30min, but the index has a frequency of 1h
        api.data.index = pd.DatetimeIndex(
            ["2020-01-01 00:00:00", "2020-01-01 01:00:00", "2020-01-01 02:00:00"],
            freq="1h",
        )
        with pytest.raises(WeatherAPIError, match="!= source freq"):
            api.get_weather()

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
        self, weather_obj: WeatherAPI, weather_df: pd.DataFrame, irradiance_method: str
    ) -> None:
        """Test the cloud_cover_to_irradiance function."""
        irradiance = weather_obj.cloud_cover_to_irradiance(
            weather_df["cloud_cover"], irradiance_method
        )
        assert isinstance(irradiance, pd.DataFrame)
        assert irradiance.shape[0] == weather_df.shape[0]
        assert irradiance.shape[1] == 3
        assert set(irradiance.columns) == {"ghi", "dni", "dhi"}
        assert irradiance.index.equals(weather_df.index)

    def test_weather_cloud_cover_to_irradiance_error(
        self, weather_obj: WeatherAPI, weather_df: pd.DataFrame
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

    @pytest.mark.parametrize(
        "freq_opt, freq", [(None, "30T"), ("30T", None), ("30T", "30T")]
    )
    def test_add_freq(
        self, weather_obj: WeatherAPI, freq_opt: str | None, freq: str | None
    ) -> None:
        """Test the add_freq function."""
        index = pd.DatetimeIndex(
            ["2020-01-01 00:00:00", "2020-01-01 00:30:00", "2020-01-01 01:00:00"],
            tz="UTC",
            freq=freq_opt,
        )
        if freq_opt is None:
            assert index.freq is None
        else:
            assert index.freq.freqstr == freq_opt
        weather_df = weather_obj._add_freq(index, freq)
        assert weather_df.freq == "30T"

    @pytest.mark.parametrize(
        "from_unit, to_unit, expected",
        valid_temperature_test_cases + valid_speed_test_cases,
    )
    def test_valid_conversion(
        self,
        weather_obj_fixed_loc: WeatherAPI,
        from_unit: str,
        to_unit: str,
        expected: pd.Series,
    ) -> None:
        result = weather_obj_fixed_loc.convert_unit(
            self.unit_conv_data, from_unit, to_unit
        )
        pd.testing.assert_series_equal(
            result,
            expected,
            check_dtype=False,
            atol=0.01,
            check_exact=False,
            check_names=False,
        )

    @pytest.mark.parametrize(
        "from_unit, to_unit", invalid_temperature_test_cases + invalid_speed_test_cases
    )
    def test_invalid_conversion(
        self, weather_obj_fixed_loc: WeatherAPI, from_unit: str, to_unit: str
    ) -> None:
        with pytest.raises(ValueError):
            weather_obj_fixed_loc.convert_unit(self.unit_conv_data, from_unit, to_unit)

    def test_invalid_data_type(self, weather_obj_fixed_loc: WeatherAPI) -> None:
        with pytest.raises(TypeError):
            weather_obj_fixed_loc.convert_unit([0, 25, 100, 37], "C", "F")


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
