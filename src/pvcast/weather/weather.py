"""Read weather forecast data and put it into a format that can be used by the pvcast module."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import InitVar, dataclass, field
from typing import Any, Tuple, Union

import numpy as np
import pandas as pd
import requests
from pandas import DataFrame, DatetimeIndex, Series, Timedelta, Timestamp
from pvlib.irradiance import campbell_norman, disc, get_extra_radiation
from pvlib.location import Location
from pytz import BaseTzInfo

_LOGGER = logging.getLogger(__name__)


@dataclass
class WeatherAPI(ABC):
    """Abstract WeatherAPI class."""

    # require lat, lon to have at least 2 decimal places of precision
    location: Location
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

    def cloud_cover_to_irradiance(self, cloud_cover: Series, how: str = "clearsky_scaling", **kwargs):
        """
        Convert cloud cover to irradiance. A wrapper method.

        NB: Code copied from pvlib.forecast as the pvlib forecast module is deprecated as of pvlib 0.9.1!

        :param cloud_cover: Cloud cover as a pandas Series
        :param how: Selects the method for conversion. Can be one of clearsky_scaling or campbell_norman.
        :param **kwargs: Passed to the selected method.
        :return: Irradiance, columns include ghi, dni, dhi.
        """
        how = how.lower()
        if how == "clearsky_scaling":
            irrads = self._cloud_cover_to_irradiance_clearsky_scaling(cloud_cover, **kwargs)
        elif how == "campbell_norman":
            irrads = self._cloud_cover_to_irradiance_campbell_norman(cloud_cover, **kwargs)
        else:
            raise ValueError(f"Invalid how argument: {how}")

        return irrads

    def _cloud_cover_to_irradiance_clearsky_scaling(self, cloud_cover: Series, method="linear", **kwargs):
        """ """
        solpos = self.location.get_solarposition(cloud_cover.index)
        cs = self.location.get_clearsky(cloud_cover.index, model="ineichen", solar_position=solpos)

        method = method.lower()
        if method == "linear":
            ghi = self._cloud_cover_to_ghi_linear(cloud_cover, cs["ghi"], **kwargs)
        else:
            raise ValueError(f"Invalid method argument: {method}")

        dni = disc(ghi, solpos["zenith"], cloud_cover.index)["dni"]
        dhi = ghi - dni * np.cos(np.radians(solpos["zenith"]))

        irrads = pd.DataFrame({"ghi": ghi, "dni": dni, "dhi": dhi}).fillna(0)
        return irrads

    def _cloud_cover_to_irradiance_campbell_norman(self, cloud_cover: Series, **kwargs):
        """ """
        solar_position = self.location.get_solarposition(cloud_cover.index)
        dni_extra = get_extra_radiation(cloud_cover.index)

        transmittance = self.cloud_cover_to_transmittance_linear(cloud_cover, **kwargs)

        irrads = campbell_norman(solar_position["apparent_zenith"], transmittance, dni_extra=dni_extra)
        irrads = irrads.fillna(0)

        return irrads

    def _cloud_cover_to_ghi_linear(self, cloud_cover: Series, ghi_clear, offset=35, **kwargs):
        """Convert cloud cover to GHI using a linear relationship."""
        offset = offset / 100.0
        cloud_cover = cloud_cover / 100.0
        ghi = (offset + (1 - offset) * (1 - cloud_cover)) * ghi_clear
        return ghi

    def cloud_cover_to_transmittance_linear(self, cloud_cover: Series, offset: float = 0.75, **kwargs):
        """
        Convert cloud cover (percentage) to atmospheric transmittance
        using a linear model.

        :param cloud_cover: Cloud cover in [%] as a pandas Series.
        :param offset: Determines the maximum transmittance for the linear model.
        :return: Atmospheric transmittance as a pandas Series.
        """
        return ((100.0 - cloud_cover) / 100.0) * offset


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
