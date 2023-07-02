"""Read weather forecast data and put it into a format that can be used by the pvcast module."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import requests
from pandas import DataFrame, DatetimeIndex, Series, Timedelta, Timestamp
from pvlib.irradiance import campbell_norman, disc, get_extra_radiation
from pvlib.location import Location
from voluptuous import All, Datetime, In, Range, Required, Schema

_LOGGER = logging.getLogger(__name__)

# schema for weather data
WEATHER_SCHEMA = Schema(
    {
        Required("source"): str,
        Required("frequency"): In(["15Min", "30Min", "1H", "1D", "1W", "M", "Y"]),
        Required("data"): [
            {
                Required("datetime"): All(str, Datetime(format="%Y-%m-%dT%H:%M:%S.%fZ")),  # RFC 3339
                Required("temperature"): All(float, Range(min=-100, max=100)),
                Required("humidity"): All(float, Range(min=0, max=100)),
                Required("wind_speed"): All(float, Range(min=0)),
                Required("cloud_coverage"): All(float, Range(min=0, max=100)),
            }
        ],
    }
)


@dataclass
class WeatherAPI(ABC):
    """Abstract WeatherAPI class.

    Source datetime strings source_dates should be created in the format "%Y-%m-%dT%H:%M:%S+00:00" (RFC 3339).

    All datetime dependent internal computations are performed with UTC timezone as reference.
    We assume the start time of the forecast is floor(current time) to the neareast hour 1H. The end time is then:
    start time + max_forecast_days - freq. For example, if the current time in CET is 19:30, the frequency is 1 hour and
    we forecast for one day the start time is then 17:00 UTC and the end time is 16:00 UTC tomorrow.
    The forecast is thus from 17:00 UTC to 16:00 UTC the next day. If the frequency was 30 minutes, the forecast would
    be from 17:00 UTC to 16:30 UTC the next day.

    The assumption to start the forecast at the floor of the current hour seems to be reasonable based on sources used
    so far. If for any reason we have to deviate from this assumption or the weather data source does not provide data
    for the current hour, the implementation of this class should be changed accordingly and a custom source_dates
    property implemented in the subclass.
    """

    # require lat, lon to have at least 2 decimal places of precision
    location: Location
    format_url: bool = field(default=True)  # whether to format the url with lat, lon, alt. Mostly for testing.

    # maximum number of days to include in the forecast
    max_forecast_days: Timedelta = field(default=Timedelta(days=7))

    # frequency of the source data and the output data
    freq_source: str = field(default="1H")  # frequency of the source data. This is fixed!
    freq_output: str = field(default="1H")  # frequency of the output data. Can be changed by user.

    # url
    _url_base: str = field(default=None, init=False)  # base url to the API
    _url: str = field(default=None, init=False)  # url to the API

    # maximum age of weather data in seconds
    max_age: Timedelta = field(default=Timedelta(hours=1))
    _last_update: Timestamp = field(default=Timestamp(0), init=False)  # last time the weather data was updated

    # raw response data from the API
    _raw_data: requests.Response = field(default=None, init=False)

    def __post_init__(self) -> None:
        self._url = self._url_formatter() if self.format_url else self._url_base

    @property
    def start_forecast(self) -> Timestamp:
        """Get the start date of the forecast."""
        return Timestamp.utcnow().floor("1H")

    @property
    def end_forecast(self) -> Timestamp:
        """Get the end date of the forecast."""
        return self.start_forecast + self.max_forecast_days

    @property
    def source_dates(self) -> DatetimeIndex:
        """Get the datetimeindex to store the forecast."""
        return pd.date_range(self.start_forecast, self.end_forecast, freq=self.freq_source, tz="UTC")

    @abstractmethod
    def _process_data(self) -> DataFrame:
        """Process data from the weather API.

        The index of the returned dataframe should be a DatetimeIndex in local time.

        :return: The weather data as a dataframe where the index is the datetime and the columns are the variables.
        """

    def get_weather(self, live: bool = False) -> dict:
        """
        Get weather data from API response. This function will always return data return in UTC.

        :param live: Before returning weather data force a weather API update.
        :return: The weather data as a dataframe where the index is the datetime and the columns are the variables.
        """
        # get weather API data, if needed. If not, use cached data.
        _LOGGER.debug("Getting weather data, force live data=%s", live)
        response: requests.Response = self._api_request_if_needed(live)

        # handle errors from the API
        self._api_error_handler(response)

        # process and return the data
        processed_data: DataFrame = self._process_data()
        if not (processed_data.index == self.source_dates).all():
            raise WeatherAPIError("Source dates do not match processed data.")

        # resample to the output frequency and interpolate
        resampled: DataFrame = processed_data.resample(self.freq_output).interpolate(method="linear").iloc[:-1]
        resampled = resampled.tz_convert("UTC")
        resampled["datetime"] = resampled.index.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        # convert to dictionary and validate schema
        try:
            data_dict = {
                "source": self.__class__.__name__,
                "frequency": self.freq_output,
                "data": resampled.to_dict(orient="records"),
            }
            WEATHER_SCHEMA(data_dict)
        except Exception as exc:
            raise WeatherAPIError("Weather data does not match schema.") from exc

        return data_dict

    def _api_request_if_needed(self, live: bool = False) -> requests.Response:
        """Check if we need to do a request or not when weather data is outdated.

        :param live: Force an update by ignoring the max_age.
        """

        if self._raw_data is not None and Timestamp.now(tz="UTC") - self._last_update < self.max_age and not live:
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
        """
        Convert cloud cover to irradiance using the clearsky scaling method.

        :param cloud_cover: Cloud cover as a pandas Series
        :param method: Selects the method for conversion. Can be one of linear.
        :param **kwargs: Passed to the selected method.
        :return: Irradiance, columns include ghi, dni, dhi.
        """
        solpos = self.location.get_solarposition(cloud_cover.index)
        clear_sky = self.location.get_clearsky(cloud_cover.index, model="ineichen", solar_position=solpos)

        method = method.lower()
        if method == "linear":
            ghi = self._cloud_cover_to_ghi_linear(cloud_cover, clear_sky["ghi"], **kwargs)
        else:
            raise ValueError(f"Invalid method argument: {method}")

        dni = disc(ghi, solpos["zenith"], cloud_cover.index)["dni"]
        dhi = ghi - dni * np.cos(np.radians(solpos["zenith"]))

        irrads = pd.DataFrame({"ghi": ghi, "dni": dni, "dhi": dhi}).fillna(0)
        return irrads

    def _cloud_cover_to_irradiance_campbell_norman(self, cloud_cover: Series, **kwargs):
        """
        Convert cloud cover to irradiance using the Campbell and Norman model.

        :param cloud_cover: Cloud cover in [%] as a pandas Series.
        :param **kwargs: Passed to the selected method.
        :return: Irradiance as a pandas DataFrame with columns ghi, dni, dhi.
        """
        solar_position = self.location.get_solarposition(cloud_cover.index)
        dni_extra = get_extra_radiation(cloud_cover.index)

        transmittance = self.cloud_cover_to_transmittance_linear(cloud_cover, **kwargs)

        irrads = campbell_norman(solar_position["apparent_zenith"], transmittance, dni_extra=dni_extra)
        irrads = irrads.fillna(0)

        return irrads

    def _cloud_cover_to_ghi_linear(self, cloud_cover: Series, ghi_clear: Series, offset=35):
        """
        Convert cloud cover to GHI using a linear relationship.

        :param cloud_cover: Cloud cover in [%] as a pandas Series.
        :param ghi_clear: Clear sky GHI as a pandas Series.
        :param offset: Determines the maximum GHI for the linear model.
        :return: GHI as a pandas Series.
        """
        offset = offset / 100.0
        cloud_cover = cloud_cover / 100.0
        ghi = (offset + (1 - offset) * (1 - cloud_cover)) * ghi_clear
        return ghi

    def cloud_cover_to_transmittance_linear(self, cloud_cover: Series, offset: float = 0.75):
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


@dataclass(frozen=True)
class WeatherAPIFactory:
    """Factory class for weather APIs."""

    _apis: dict[str, WeatherAPI] = field(default_factory=dict)

    def register(self, api_id: str, weather_api_class: WeatherAPI) -> None:
        """
        Register a new weather API class to the factory.

        :param api_id: The identifier string of the API which is used in config.yaml.
        :param weather_api_class: The weather API class.
        """
        self._apis[api_id] = weather_api_class

    def get_weather_api(self, api_id: str, **kwargs) -> WeatherAPI:
        """
        Get a weather API instance.

        :param api_id: The identifier string of the API which is used in config.yaml.
        :param **kwargs: Passed to the weather API class.
        :return: The weather API instance.
        """
        try:
            weather_api_class = self._apis[api_id]
        except KeyError as exc:
            raise ValueError(f"Unknown weather API: {api_id}") from exc

        return weather_api_class(**kwargs)
