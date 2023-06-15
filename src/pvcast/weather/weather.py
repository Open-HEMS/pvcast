"""Read weather forecast data and put it into a format that can be used by the pvcast module."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Tuple

import pandas as pd
import requests
from pandas import DataFrame, DatetimeIndex, Timedelta, Timestamp

_LOGGER = logging.getLogger(__name__)


@dataclass
class WeatherAPI(ABC):
    """Abstract WeatherAPI class."""

    # require lat, lon to have at least 2 decimal places of precision
    lat: float
    lon: float
    alt: float = field(default=0.0)
    format_url: bool = field(default=True)  # whether to format the url with lat, lon, alt. Mostly for testing.

    # url
    _url_base: str = field(default=None, init=False)  # base url to the API
    _url: str = field(default=None, init=False)  # url to the API

    # maximum age of weather data in seconds
    max_age: Timedelta = field(default=Timedelta(hours=1))
    _last_update: Timestamp = field(default=None, init=False)

    # raw response data from the API
    _raw_data: requests.Response = field(default=None, init=False)

    @property
    def start_forecast(self) -> Timestamp:
        """Get the start date of the forecast."""
        return Timestamp.now(tz="UTC").floor("D")

    @property
    def end_forecast(self) -> DatetimeIndex:
        """Get the end date of the forecast."""
        return self.start_forecast + Timedelta(days=1)

    @property
    def forecast_dates(self) -> DatetimeIndex:
        """Get the dates of the forecast."""
        return pd.date_range(self.start_forecast, self.end_forecast, freq="H")

    @property
    def location(self) -> tuple[float, float, float]:
        """Get the location of the forecast in the format (lat, lon, alt)."""
        return (self.lat, self.lon, self.alt)

    @abstractmethod
    def _process_data(self) -> DataFrame:
        """Process data from the weather API.

        :return: The weather data as a dataframe where the index is the datetime and the columns are the variables.
        """

    def get_weather(self) -> DataFrame:
        """Get weather data from API response.

        :return: The weather data as a dataframe where the index is the datetime and the columns are the variables.
        """
        # get weather API data, if needed. If not, use cached data.
        response = self._api_request_if_needed()

        # handle errors from the API
        self._api_error_handler(response)

        # process and return the data
        try:
            return self._process_data()
        except Exception as e:
            _LOGGER.error(f"Error processing data: {e}")
            raise e

    # url formatter function
    def __post_init__(self) -> None:
        """Post init function."""
        if self.format_url:
            self._url = self._url_formatter()
        else:
            self._url = self._url_base

    @abstractmethod
    def _url_formatter(self) -> str:
        """Format the url to the API."""

    @staticmethod
    def _api_error_handler(response: requests.Response) -> None:
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

    def _api_request_if_needed(self) -> requests.Response:
        """Check if we need to do a request or not when weather data is outdated."""

        if self._raw_data is not None and Timestamp.now(tz="UTC") - self._last_update < self.max_age:
            _LOGGER.debug("Using cached weather data.")
            return self._raw_data

        # do the request
        try:
            response = requests.get(self._url, timeout=10)
        except requests.exceptions.Timeout as exc:
            raise WeatherAPIErrorTimeout() from exc

        # request error handling
        self._api_error_handler(response)

        # return the response
        self._raw_data = response
        self._last_update = Timestamp.now(tz="UTC")
        return response


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
