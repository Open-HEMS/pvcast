"""Read weather forecast data and put it into a format that can be used by the pvcast module."""

from __future__ import annotations

import datetime as dt
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import timezone as tz
from typing import Any, Callable

import numpy as np
import polars as pl
import requests
from pvlib.irradiance import campbell_norman, disc, get_extra_radiation
from pvlib.location import Location
from requests import Response
from voluptuous import All, Datetime, Optional, Range, Required, Schema

from ..util.timestamps import timedelta_to_pl_duration

_LOGGER = logging.getLogger(__name__)

# schema for weather data
WEATHER_SCHEMA = Schema(
    {
        Required("source"): str,
        Required("interval"): str,
        Required("data"): [
            {
                Required("datetime"): All(
                    str, Datetime(format="%Y-%m-%dT%H:%M:%S%z")
                ),  # RFC 3339
                Required("temperature"): All(float, Range(min=-100, max=100)),
                Required("humidity"): All(int, Range(min=0, max=100)),
                Required("wind_speed"): All(float, Range(min=0)),
                Required("cloud_coverage"): All(int, Range(min=0, max=100)),
                Optional("ghi"): All(float, Range(min=0)),
                Optional("dni"): All(float, Range(min=0)),
                Optional("dhi"): All(float, Range(min=0)),
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

    NOTE: Because of the order in which dataclasses are initialized, a subclass of WeatherAPI can't have
    non-default attributes. See also: https://stackoverflow.com/questions/51575931
    """

    # require lat, lon to have at least 2 decimal places of precision
    location: Location
    url: str

    # weather API source type identifier
    sourcetype: str = field(default="")

    # weather API unique name
    name: str = field(default="")

    # timeout in seconds for the API request
    timeout: dt.timedelta = field(default=dt.timedelta(seconds=10))

    # maximum number of days to include in the forecast
    max_forecast_days: dt.timedelta = field(default=dt.timedelta(days=7))

    # frequency of the source data. This is fixed!
    freq_source: dt.timedelta = field(default=dt.timedelta(hours=1))

    # maximum age of weather data before requesting new data
    max_age: dt.timedelta = field(default=dt.timedelta(hours=1))

    # last time the weather data was updated
    _last_update: dt.datetime = field(default=dt.datetime(1970, 1, 1, tzinfo=tz.utc))

    # raw response data from the API
    _raw_data: Response | None = field(default=None, init=False)

    @property
    def last_update(self) -> dt.datetime:
        """Get the last time the weather data was updated."""
        return self._last_update

    @property
    def start_forecast(self) -> dt.datetime:
        """Get the start date of the forecast."""
        return dt.datetime.now(tz.utc).replace(minute=0, second=0, microsecond=0)

    @property
    def end_forecast(self) -> dt.datetime:
        """Get the end date of the forecast."""
        return self.start_forecast + self.max_forecast_days - self.freq_source

    @property
    def source_dates(self) -> pl.Series:
        """
        Get the pl.DatetimeIndex to store the forecast. These are only used if missing from API, the weather API can
        also return datetime strings and in that case this index is not needed and even not preferred.
        """
        return self.get_source_dates(
            self.start_forecast, self.end_forecast, self.freq_source
        )

    @staticmethod
    def get_source_dates(
        start: dt.datetime, end: dt.datetime, inter: dt.timedelta
    ) -> pl.Series:
        """
        Get the pl.DatetimeIndex to store the forecast. These are only used if missing from API, the weather API can
        also return datetime strings and in that case this index is not needed and even not preferred.
        """
        return pl.datetime_range(
            start, end, inter, time_zone=str(dt.timezone.utc), eager=True
        )

    @abstractmethod
    def _process_data(self) -> pl.DataFrame:
        """Process data from the weather API.

        The index of the returned pl.DataFrame should be a pl.DatetimeIndex in local time.

        :return: The weather data as a pl.DataFrame where the index is the datetime and the columns are the variables.
        """

    def get_weather(
        self, live: bool = False, calc_irrads: bool = False
    ) -> dict[str, Any]:
        """
        Get weather data from API response. This function will always return data return in UTC.

        :param live: Before returning weather data force a weather API update.
        :param calc_irrads: Whether to calculate irradiance from cloud cover and add it to the weather data.
        :return: The weather data as a dict.
        """
        # get weather API data, if needed. If not, use cached data.
        _LOGGER.debug("Getting weather data, force live data=%s", live)
        response: Response = self._api_request_if_needed(live)

        # handle errors from the API
        self._api_error_handler(response)

        # process and return the data
        processed_data: pl.DataFrame = self._process_data()

        # verify that data has a "datetime" column, all data is unique, sorted and in UTC

        if "datetime" not in processed_data.columns:
            raise WeatherAPIError("Processed data does not have a datetime column.")
        if not all(processed_data["datetime"].is_unique()):
            raise WeatherAPIError("Processed data contains duplicate datetimes.")
        if not processed_data["datetime"].is_sorted():
            raise WeatherAPIError("Processed data is not sorted.")
        dt_type = processed_data["datetime"].dtype
        if dt_type != pl.Datetime:
            raise WeatherAPIError(f"Datetime type should be pl.Datetime, is {dt_type}.")
        if processed_data["datetime"].dtype.time_zone != str(dt.timezone.utc):
            raise WeatherAPIError("Datetime column is not in UTC.")
        if not all(processed_data["datetime"].diff()[1:] == self.freq_source):
            raise WeatherAPIError("Processed data contains gaps.")
        if any(col.has_validity() for col in processed_data):
            raise WeatherAPIError("Processed data contains NaN values.")

        # cut off the data that exceeds max_forecast_days
        processed_data = processed_data.filter(pl.col("datetime") <= self.end_forecast)

        # set data types
        processed_data = processed_data.cast(
            {
                "cloud_coverage": int,
                "humidity": int,
                "temperature": float,
                "wind_speed": float,
            }
        )

        # calculate irradiance from cloud cover
        if calc_irrads:
            _LOGGER.debug("Calculating irradiance from cloud cover.")
            irrads = self.cloud_cover_to_irradiance(processed_data["cloud_coverage"])
            processed_data = pl.concat([processed_data, irrads], how="horizontal")

        # convert datetime column to str
        processed_data = processed_data.with_columns(
            processed_data["datetime"].dt.strftime("%Y-%m-%dT%H:%M:%S%z")
        )

        # convert to dictionary and validate schema
        data_dict = processed_data.to_dict(as_series=False)
        data_dict = [dict(zip(data_dict, t)) for t in zip(*data_dict.values())]
        try:
            data_dict = {
                "source": self.__class__.__name__,
                "interval": timedelta_to_pl_duration(self.freq_source),
                "data": data_dict,
            }
            WEATHER_SCHEMA(data_dict)
        except Exception as exc:
            raise WeatherAPIError(
                f"Error validating weather data: {data_dict}"
            ) from exc

        return data_dict

    def _api_request_if_needed(self, live: bool = False) -> Response:
        """Check if we need to do a request or not when weather data is outdated.

        :param live: Force an update by ignoring self.max_age.
        """
        delta_t = dt.datetime.now(tz.utc) - self._last_update
        if self._raw_data is not None and delta_t < self.max_age and not live:
            _LOGGER.debug("Using cached weather data.")
            return self._raw_data

        _LOGGER.debug(
            "Getting weather data from API. [dT = %ssec, max_age = %ssec, live = %s, raw_data = %s]",
            round(delta_t.total_seconds(), 1),
            round(self.max_age.total_seconds(), 1),
            live,
            self._raw_data is not None,
        )

        # do the request
        try:
            response = self._do_request()
        except requests.exceptions.Timeout as exc:
            raise WeatherAPIErrorTimeout() from exc

        # request error handling
        self._api_error_handler(response)

        # return the response
        self._raw_data = response
        self._last_update = dt.datetime.now(tz.utc)
        return response

    def _do_request(self) -> Response:
        """
        Make GET request to weather API and return the response.
        Can be overridden by subclasses if needed.

        :return: Response from weather API.
        """
        return requests.get(self.url, timeout=self.timeout)

    @staticmethod
    def _api_error_handler(response: Response) -> None:
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
                raise WeatherAPIError("Unknown error", response.status_code)

    def cloud_cover_to_irradiance(
        self, cloud_cover: pl.Series, how: str = "clearsky_scaling", **kwargs: Any
    ) -> pl.DataFrame:
        """
        Convert cloud cover to irradiance. A wrapper method.

        NB: Code copied from pvlib.forecast as the pvlib forecast module is deprecated as of pvlib 0.9.1!

        :param cloud_cover: Cloud cover as a pandas pl.Series
        :param how: Selects the method for conversion. Can be one of clearsky_scaling or campbell_norman.
        :param **kwargs: Passed to the selected method.
        :return: Irradiance, columns include ghi, dni, dhi.
        """
        how = how.lower()
        if how == "clearsky_scaling":
            irrads = self._cloud_cover_to_irradiance_clearsky_scaling(
                cloud_cover, **kwargs
            )
        elif how == "campbell_norman":
            irrads = self._cloud_cover_to_irradiance_campbell_norman(
                cloud_cover, **kwargs
            )
        else:
            raise ValueError(f"Invalid how argument: {how}")
        return irrads

    def _cloud_cover_to_irradiance_clearsky_scaling(
        self, cloud_cover: pl.Series, method: str = "linear", **kwargs: Any
    ) -> pl.DataFrame:
        """
        Convert cloud cover to irradiance using the clearsky scaling method.

        :param cloud_cover: Cloud cover as a pandas pl.Series
        :param method: Selects the method for conversion. Can be one of linear.
        :param **kwargs: Passed to the selected method.
        :return: Irradiance, columns include ghi, dni, dhi.
        """
        solpos = self.location.get_solarposition(cloud_cover.index)
        clear_sky = self.location.get_clearsky(
            cloud_cover.index, model="ineichen", solar_position=solpos
        )

        method = method.lower()
        if method == "linear":
            ghi = self._cloud_cover_to_ghi_linear(
                cloud_cover, clear_sky["ghi"], **kwargs
            )
        else:
            raise ValueError(f"Invalid method argument: {method}")

        dni = disc(ghi, solpos["zenith"], cloud_cover.index)["dni"]
        dhi = ghi - dni * np.cos(np.radians(solpos["zenith"]))

        irrads = pl.DataFrame({"ghi": ghi, "dni": dni, "dhi": dhi}).fill_null(0)
        return irrads

    def _cloud_cover_to_irradiance_campbell_norman(
        self, cloud_cover: pl.Series, **kwargs: Any
    ) -> pl.DataFrame:
        """
        Convert cloud cover to irradiance using the Campbell and Norman model.

        :param cloud_cover: Cloud cover in [%] as a pandas pl.Series.
        :param **kwargs: Passed to the selected method.
        :return: Irradiance as a pandas pl.DataFrame with columns ghi, dni, dhi.
        """
        solar_position = self.location.get_solarposition(cloud_cover.index)
        dni_extra = get_extra_radiation(cloud_cover.index)

        transmittance = self.cloud_cover_to_transmittance_linear(cloud_cover, **kwargs)

        irrads = campbell_norman(
            solar_position["apparent_zenith"], transmittance, dni_extra=dni_extra
        )
        irrads = irrads.fillna(0)
        return pl.from_pandas(irrads)

    def _cloud_cover_to_ghi_linear(
        self, cloud_cover: pl.Series, ghi_clear: pl.Series, offset: float = 35.0
    ) -> pl.Series:
        """
        Convert cloud cover to GHI using a linear relationship.

        :param cloud_cover: Cloud cover in [%] as a pandas pl.Series.
        :param ghi_clear: Clear sky GHI as a pandas pl.Series.
        :param offset: Determines the maximum GHI for the linear model.
        :return: GHI as a pandas pl.Series.
        """
        offset = offset / 100.0
        cloud_cover = cloud_cover / 100.0
        ghi = (offset + (1 - offset) * (1 - cloud_cover)) * ghi_clear
        return ghi

    def cloud_cover_to_transmittance_linear(
        self, cloud_cover: pl.Series, offset: float = 0.75
    ) -> pl.Series:
        """
        Convert cloud cover (percentage) to atmospheric transmittance
        using a linear model.

        :param cloud_cover: Cloud cover in [%] as a pandas pl.Series.
        :param offset: Determines the maximum transmittance for the linear model.
        :return: Atmospheric transmittance as a pandas pl.Series.
        """
        return ((100.0 - cloud_cover) / 100.0) * offset


@dataclass(frozen=True)
class WeatherAPIError(Exception):
    """Exception class for weather API errors."""

    message: str = field(default="Weather API error")
    error: int = field(default=-1)


@dataclass(frozen=True)
class WeatherAPIErrorNoData(WeatherAPIError):
    """Exception class for weather API errors."""

    message: str = field(default="No weather data available")

    @classmethod
    def from_date(cls, date: str) -> WeatherAPIErrorNoData:
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

    _apis: dict[str, Callable[..., WeatherAPI]] = field(default_factory=dict)

    def register(
        self, api_id: str, weather_api_class: Callable[..., WeatherAPI]
    ) -> None:
        """
        Register a new weather API class to the factory.

        :param api_id: The identifier string of the API which is used in config.yaml.
        :param weather_api_class: The weather API class.
        """
        self._apis[api_id] = weather_api_class

    def get_weather_api(self, api_id: str, **kwargs: Any) -> WeatherAPI:
        """
        Get a weather API instance.

        :param api_id: The identifier string of the API which is used in config.yaml.
        :param **kwargs: Passed to the weather API class.
        :return: The weather API instance.
        """
        try:
            weather_api_class: Callable[..., WeatherAPI] = self._apis[api_id]
        except KeyError as exc:
            raise ValueError(f"Unknown weather API: {api_id}") from exc

        return weather_api_class(**kwargs)

    def get_weather_api_list_obj(self) -> list[Callable[..., WeatherAPI]]:
        """
        Get a list of all registered weather API instances.

        :return: List of weather API identifiers.
        """
        return list(self._apis.values())

    def get_weather_api_list_str(self) -> list[str]:
        """
        Get a list of all registered weather API identifiers.

        :return: List of weather API identifiers.
        """
        return list(self._apis.keys())
