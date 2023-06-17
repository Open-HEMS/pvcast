"""Test the weather module."""
from __future__ import annotations

import pytest
from const import LOC_EUW
from pandas import DataFrame

from pvcast.weather.clearoutside import WeatherAPIClearOutside

# class TestWeatherClearOutside:
#     """Test the clear outside weather module."""

#     @pytest.fixture()
#     def weather_co_wrong_url():
#         """Fixture for the Clear Outside weather API with no data."""
#         obj = WeatherAPIClearOutside(*LOC_EUW)

#         # set the url to a wrong url (require replace() bc dataclass is frozen)
#         return replace(obj, url_base="https://clearoutside.com/wrongcast/")

#     def test_weather_weather_data_cache(self, weather_co):
#         """Test the get_weather function."""

#         # get first weather data object
#         weather1 = weather_co.get_weather()
#         assert isinstance(weather1, DataFrame)
#         last_update1 = weather_co._last_update
#         print(f"last_update1: {weather_co._last_update}")

#         # get second weather data object, should see that it is cached data
#         weather2 = weather_co.get_weather()
#         assert isinstance(weather2, DataFrame)
#         last_update2 = weather_co._last_update
#         print(f"last_update2: {weather_co._last_update}")
#         assert last_update1 == last_update2