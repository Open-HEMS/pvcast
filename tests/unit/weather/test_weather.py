"""Test the weather module."""
from __future__ import annotations

import datetime as dt

import polars as pl
import pytest
from pvlib.location import Location

from pvcast.weather.weather import WeatherAPI, WeatherAPIError, WeatherAPIFactory

TEST_URL = "http://fakeurl.com/status/"


@pytest.fixture
def weather_api(location: Location, data: pl.DataFrame) -> WeatherAPI:
    """Get a weather API object."""
    return MockWeatherAPI(location=location, url=TEST_URL, data=data)


# mock for WeatherAPI class
class MockWeatherAPI(WeatherAPI):
    """Mock the WeatherAPI class."""

    def __init__(self, location: Location, url: str, data: pl.DataFrame) -> None:
        """Initialize the mock class."""
        super().__init__(location, url, freq_source=dt.timedelta(minutes=30))
        self.url = url
        self.data = data

    def retrieve_new_data(self) -> pl.DataFrame:
        """Retrieve new data from the API."""
        return self.data


class CommonWeatherTests:
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


class TestWeatherAPI(CommonWeatherTests):
    """Test the weather module."""

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
        "data, error_match",
        [
            (mock_data_NaN, "Processed data contains NaN values."),
            (mock_data_invalid, "Error validating weather data:"),
        ],
        indirect=["data"],
    )
    def test_get_weather(
        self, weather_api: WeatherAPI, data: pl.DataFrame, error_match: str
    ) -> None:
        """Test the get_weather function with different input data."""
        with pytest.raises(WeatherAPIError, match=error_match):
            weather_api.get_weather()


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
                "mock",
                location=Location(0, 0, "UTC", 0),
                url=TEST_URL,
                data=TestWeatherAPI.mock_data,
            ),
            MockWeatherAPI,
        )
        with pytest.raises(ValueError):
            weather_api_factory.get_weather_api(
                "wrong_api",
                location=Location(0, 0, "UTC", 0),
                url=TEST_URL,
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
