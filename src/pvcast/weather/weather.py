"""Read weather forecast data and put it into a format that can be used by the pvcast module."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Tuple

import pandas as pd
import requests

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class WeatherAPI(ABC):
    """Abstract WeatherAPI class."""

    # require lat, lon to have at least 2 decimal places of precision
    lat: float
    lon: float
    alt: float = field(default=0.0)
    format_url: bool = field(default=True)  # whether to format the url with lat, lon, alt. Mostly for testing.

    @property
    def start_forecast(self) -> pd.Timestamp:
        """Get the start date of the forecast.

        :return: The start date of the forecast.
        """
        return pd.Timestamp.now(tz="UTC").floor("D")

    @property
    def end_forecast(self) -> pd.Timestamp:
        """Get the end date of the forecast.

        :return: The end date of the forecast.
        """
        return self.start_forecast + pd.Timedelta(days=1)

    @property
    def forecast_dates(self) -> pd.DatetimeIndex:
        """Get the dates of the forecast.

        :return: The dates of the forecast.
        """
        return pd.date_range(self.start_forecast, self.end_forecast, freq="H")

    @property
    def location(self) -> Tuple[float, float, float]:
        """Get the location of the forecast in the format (lat, lon, alt)."""
        return (self.lat, self.lon, self.alt)

    @abstractmethod
    def _do_api_request(self) -> requests.Response:
        """Do a request to the API and store the response in self._response.

        :return: The API data.
        """

    @abstractmethod
    def get_weather(self) -> pd.DataFrame:
        """Get weather data from API response.

        :return: The weather data as a dictionary where the format is: {"date": {"variable": value}}.
        """

    @staticmethod
    def api_error_handler(response: requests.Response) -> None:
        """Handle errors from the API.

        :param response: The response from the API.
        :raises WeatherAPIError: If the response is not 200.
        """
        if response.status_code != 200:
            if response.status_code == 404:
                raise WeatherAPIErrorWrongURL()
            elif response.status_code == 429:
                raise WeatherAPIErrorTooManyReq()
            else:
                raise WeatherAPIError(response.status_code)


@dataclass(frozen=True)
class WeatherAPIError(Exception):
    """Exception class for weather API errors."""

    error: int
    message: str = field(default="Weather API error")


@dataclass(frozen=True)
class WeatherAPIErrorNoData(WeatherAPIError):
    """Exception class for weather API errors."""

    message: str = field(default="No weather data available")

    @classmethod
    def from_date(cls, date: str):
        """Create an exception for a specific date.

        :param date: The date for which no weather data is available.
        :return: The exception.
        """
        return cls(f"No weather data available for {date}")


@dataclass(frozen=True)
class WeatherAPIErrorTooManyReq(WeatherAPIError):
    """Exception error 429, too many requests."""

    message: str = field(default="Too many requests")
    error: int = field(default=429)


@dataclass(frozen=True)
class WeatherAPIErrorWrongURL(WeatherAPIError):
    """Exception error 404, wrong URL."""

    message: str = field(default="Wrong URL")
    error: int = field(default=404)


@dataclass(frozen=True)
class WeatherAPIErrorTimeout(WeatherAPIError):
    """Exception error 408, timeout."""

    message: str = field(default="API timeout")
    error: int = field(default=408)


@dataclass(frozen=True)
class WeatherAPIErrorNoLocation(WeatherAPIError):
    """Exception error 404, no data for location."""

    message: str = field(default="No data for location available")
