"""Test the weather module."""
from __future__ import annotations

import datetime as dt
import typing

import numpy as np
import polars as pl
import pytest
from pvlib.location import Location

from pvcast.weather.weather import WeatherAPI, WeatherAPIError, WeatherAPIFactory
from tests.conftest import MockWeatherAPI


class CommonWeatherTests:
    """Test common weather API functionality.

    These tests can be run on both the abstract WeatherAPI class and on platforms
    that inherit from it. This class should no run platform specific tests.
    """

    common_data: typing.ClassVar[dict[str, list[float]]] = {
        "temperature": [0, 0.5, 1],
        "humidity": [0, 0.5, 1],
        "wind_speed": [0, 0.5, 1],
        "cloud_cover": [0, 0.5, 1],
    }

    def test_weather_data_cache(self, weather_api: WeatherAPI) -> None:
        """Test the get_weather function."""
        # get first weather data object
        weather1 = weather_api.get_weather()
        assert isinstance(weather1, dict)
        last_update1 = weather_api._last_update
        # get second weather data object, should see that it is cached data
        weather2 = weather_api.get_weather()
        assert isinstance(weather2, dict)
        last_update2 = weather_api._last_update
        assert last_update1 == last_update2

    def test_weather_data_live(self, weather_api: WeatherAPI) -> None:
        """Test the get_weather function."""
        weather1 = weather_api.get_weather()
        assert isinstance(weather1, dict)
        last_update1 = weather_api._last_update
        weather2 = weather_api.get_weather(live=True)
        assert isinstance(weather2, dict)
        last_update2 = weather_api._last_update
        assert last_update2 > last_update1

    def test_weather_data_outdated(self, weather_api: WeatherAPI) -> None:
        """Test the get_weather function."""
        # set max data age to -1 seconds, i.e. always outdated
        weather_api.max_age = dt.timedelta(seconds=-1)
        weather1 = weather_api.get_weather()
        assert isinstance(weather1, dict)
        last_update1 = weather_api._last_update
        weather2 = weather_api.get_weather()
        assert isinstance(weather2, dict)
        last_update2 = weather_api._last_update
        assert last_update2 > last_update1

    def test_weather_data_calc_irrads(self, weather_api: WeatherAPI) -> None:
        """Test the get_weather function."""
        weather = weather_api.get_weather(calc_irrads=True)
        assert isinstance(weather, dict)
        for datapoint in weather["data"]:
            assert "ghi" in datapoint
            assert "dni" in datapoint
            assert "dhi" in datapoint

    # indirect parametrization of data
    @pytest.mark.parametrize("weather_api_dt_missing", [common_data], indirect=True)
    def test_weather_data_no_datetime(self, weather_api_dt_missing: WeatherAPI) -> None:
        """Test the get_weather function."""
        with pytest.raises(
            WeatherAPIError, match="Processed data does not have a datetime column."
        ):
            _ = weather_api_dt_missing.get_weather()

    @pytest.mark.parametrize(
        ("data", "error_message"),
        [
            (
                {
                    **common_data,
                    "datetime": [
                        "2020-01-01T00:00:00+00:00",
                        "2020-01-01T00:00:00+00:00",
                        "2020-01-01T01:00:00+00:00",
                    ],
                },
                "Processed data contains duplicate",
            ),
            (
                {
                    **common_data,
                    "datetime": [
                        "2020-01-01T02:00:00+00:00",
                        "2020-01-01T01:00:00+00:00",
                        "2020-01-01T03:00:00+00:00",
                    ],
                },
                "Processed data is not sorted.",
            ),
            (
                {
                    **common_data,
                    "datetime": [
                        "2020-01-01T00:00:00+00:00",
                        "2020-01-01T01:00:00+00:00",
                        "2020-01-01T03:00:00+00:00",
                    ],
                },
                "Processed data contains gaps.",
            ),
        ],
    )
    def test_weather_data_processing(
        self, weather_api_fix_loc: WeatherAPI, data: pl.DataFrame, error_message: str
    ) -> None:
        """Test the get_weather function with different data scenarios."""
        weather_api_fix_loc.data = pl.DataFrame(data)
        with pytest.raises(WeatherAPIError, match=error_message):
            _ = weather_api_fix_loc.get_weather()


class TestWeatherAPI(CommonWeatherTests):
    """These tests are run on the abstract WeatherAPI class only."""

    # define test data
    mock_data = pl.DataFrame(
        {
            "temperature": [0, 0.5, 1],
            "humidity": [0, 0.5, 1],
            "wind_speed": [0, 0.5, 1],
            "cloud_cover": [0, 0.5, 1],
            "datetime": [
                "2020-01-01T00:00:00+00:00",
                "2020-01-01T00:30:00+00:00",
                "2020-01-01T01:00:00+00:00",
            ],
        }
    )

    # test data with NaN values
    mock_data_nan = pl.DataFrame(
        {
            "temperature": [None, 0.5, None],
            "humidity": [0, 0.5, 1],
            "wind_speed": [0, 0.5, 1],
            "cloud_cover": [0, 0.5, 1],
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
            "cloud_cover": [0, 0.5, 1],
            "invalid_column": [0, 0.5, 1],
            "datetime": [
                "2020-01-01T00:00:00+00:00",
                "2020-01-01T00:30:00+00:00",
                "2020-01-01T01:00:00+00:00",
            ],
        }
    )

    @pytest.fixture
    def data(self, request: pytest.FixtureRequest) -> pl.DataFrame:
        """Get test data."""
        # if request is not parametrized, use a default response
        if not hasattr(request, "param"):
            data: pl.DataFrame = self.mock_data
        else:
            data = request.param
        return data

    def test_weather_api_init(self, weather_api: WeatherAPI) -> None:
        """Test the WeatherAPI class initialization."""
        assert isinstance(weather_api, WeatherAPI)
        assert isinstance(weather_api.location, Location)

    def test_get_weather_no_update(self, weather_api: WeatherAPI) -> None:
        """Test the get_weather function without updating the data."""
        weather_api.get_weather()
        assert weather_api._last_update is not None
        t_now = dt.datetime.now(dt.timezone.utc)
        assert t_now - weather_api._last_update < dt.timedelta(seconds=1)

    @pytest.mark.parametrize(
        ("data", "error_match"),
        [
            (mock_data_nan, "Processed data contains NaN values."),
            (mock_data_invalid, "Error validating weather data:"),
        ],
        indirect=["data"],
    )
    def test_get_weather(
        self,
        weather_api: WeatherAPI,
        data: pl.DataFrame,  # noqa: ARG002
        error_match: str,
    ) -> None:
        """Test the get_weather function with different input data."""
        with pytest.raises(WeatherAPIError, match=error_match):
            weather_api.get_weather()

    @pytest.mark.parametrize("how", ["clearsky_scaling", "campbell_norman"])
    @pytest.mark.parametrize("interval_min", [1, 2, 5, 10, 15, 30, 60])
    def test_cloud_cover_to_irradiance(
        self, weather_api_fix_loc: WeatherAPI, how: str, interval_min: int
    ) -> None:
        """Test the cloud_cover_to_irradiance function."""
        interval = dt.timedelta(minutes=interval_min)

        # set frequency of source data
        weather_api_fix_loc.freq_source = interval
        n_points = int(dt.timedelta(days=2) / interval)

        # construct dataframe
        cloud_cover = pl.DataFrame(
            {
                "datetime": pl.datetime_range(
                    dt.date(2022, 1, 1),
                    dt.date(2022, 1, 3),
                    interval,
                    eager=True,
                    time_zone="UTC",
                )[0:n_points],
                "cloud_cover": list(np.linspace(0, 100, n_points)),
            }
        )

        assert isinstance(cloud_cover, pl.DataFrame)
        assert cloud_cover["cloud_cover"].dtype == pl.Float64
        irrads = weather_api_fix_loc.cloud_cover_to_irradiance(cloud_cover, how=how)
        assert isinstance(irrads, pl.DataFrame)
        for irr in ["ghi", "dni", "dhi"]:
            assert irr in irrads.columns
            assert irrads[irr].dtype == pl.Float64
            assert irrads[irr].min() >= 0  # min irradiance on earth
            assert irrads[irr].max() <= 1370  # max irradiance on earth
            assert len(irrads[irr]) == len(cloud_cover)
            assert irrads[irr].is_null().sum() == 0
            assert irrads[irr].is_nan().sum() == 0

    def test_cloud_cover_to_irradiance_invalid_how(
        self, weather_api_fix_loc: WeatherAPI
    ) -> None:
        """Test the cloud_cover_to_irradiance function with invalid how argument."""
        with pytest.raises(ValueError, match="Invalid how argument"):
            _ = weather_api_fix_loc.cloud_cover_to_irradiance(
                pl.DataFrame({"cloud_cover": [0], "datetime": ["2020-01-01"]}),
                how="invalid",
            )


class TestWeatherFactory:
    """Test the weather factory module."""

    test_url = "http://fakeurl.com/status/"

    @pytest.fixture
    def weather_api_factory(self) -> WeatherAPIFactory:
        """Get a weather API factory."""
        api_factory_test = WeatherAPIFactory()
        api_factory_test.register("mock", MockWeatherAPI)
        return api_factory_test

    def test_get_weather_api(
        self, weather_api_factory: WeatherAPIFactory, test_url: str
    ) -> None:
        """Test the get_weather_api function."""
        assert isinstance(weather_api_factory, WeatherAPIFactory)
        assert isinstance(
            weather_api_factory.get_weather_api(
                "mock",
                location=Location(0, 0, "UTC", 0),
                url=test_url,
                data=TestWeatherAPI.mock_data,
            ),
            MockWeatherAPI,
        )
        with pytest.raises(ValueError, match="Unknown weather API"):
            weather_api_factory.get_weather_api(
                "wrong_api",
                location=Location(0, 0, "UTC", 0),
                url=test_url,
                data=TestWeatherAPI.mock_data,
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
