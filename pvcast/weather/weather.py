"""Read weather forecast data and put it into a format that can be used by the pvcast module."""

from __future__ import annotations

import datetime as dt
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import timezone as tz
from typing import Any, Callable, Union

import numpy as np
import pandas as pd
import polars as pl
from pvlib.irradiance import campbell_norman, disc, get_extra_radiation
from pvlib.location import Location
from voluptuous import All, Coerce, Datetime, Optional, Range, Required, Schema

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
                Required("temperature"): All(Coerce(float), Range(min=-100, max=100)),
                Required("humidity"): All(Coerce(float), Range(min=0, max=100)),
                Required("wind_speed"): All(Coerce(float), Range(min=0)),
                Required("cloud_coverage"): All(Coerce(float), Range(min=0, max=100)),
                Optional("ghi"): All(Coerce(float), Range(0, 1400)),
                Optional("dni"): All(Coerce(float), Range(0, 1400)),
                Optional("dhi"): All(Coerce(float), Range(0, 1400)),
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
    _last_update: dt.datetime = field(
        default=dt.datetime(1970, 1, 1, tzinfo=tz.utc), repr=False, init=False
    )

    # processed weather data as list of dicts
    _weather_data: dict[str, list[dict[str, Any]] | str | None] = field(
        default_factory=dict, repr=False, init=False
    )

    @property
    def dt_new_data(self) -> dt.timedelta:
        """Get the time delta since the last update."""
        delta = dt.datetime.now(tz.utc) - self._last_update
        _LOGGER.debug("Time since last data update: %s", delta)
        return delta

    @property
    def start_forecast(self) -> dt.datetime:
        """Get the start date of the forecast."""
        return dt.datetime.now(tz.utc).replace(minute=0, second=0, microsecond=0)

    @property
    def end_forecast(self) -> dt.datetime:
        """Get the end date of the forecast."""
        return self.start_forecast + self.max_forecast_days

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
    def retrieve_new_data(self) -> pl.DataFrame:
        """
        Retrieve new weather data from the API.

        :return: Response from the API
        """

    def get_weather(
        self, live: bool = False, calc_irrads: bool = False
    ) -> dict[str, list[dict[str, Any]] | str | None]:
        """
        Get weather data from API response. This function will always return data return in UTC.

        :param live: Before returning weather data force a weather API update.
        :param calc_irrads: Whether to calculate irradiance from cloud cover and add it to the weather data.
        :return: The weather data as a dict.
        """
        # if we have valid cached data available, return it
        if len(self._weather_data) > 0 and self.dt_new_data < self.max_age and not live:
            _LOGGER.debug("Using cached weather data with age %s.", self.dt_new_data)
            return self._weather_data

        # no cached data available, retrieve new data
        _LOGGER.debug("Retrieving new weather data.")
        try:
            processed_data = self.retrieve_new_data()
            self._last_update = dt.datetime.now(tz.utc)
        except WeatherAPIErrorNoData as exc:
            raise WeatherAPIErrorNoData.from_date(self.start_forecast) from exc

        # verify that data has a "datetime" column, all data is unique and sorted
        if "datetime" not in processed_data.columns:
            raise WeatherAPIError("Processed data does not have a datetime column.")
        if not all(processed_data["datetime"].is_unique()):
            raise WeatherAPIError("Processed data contains duplicate datetimes.")
        if not processed_data["datetime"].is_sorted():
            raise WeatherAPIError("Processed data is not sorted.")
        if processed_data["datetime"].dtype != pl.Datetime:
            try:
                processed_data = processed_data.with_columns(
                    pl.col("datetime").str.to_datetime()
                )
            except Exception:
                raise WeatherAPIError(
                    f"Datetime type should be pl.Datetime, is {processed_data['datetime'].dtype}."
                )

        # check if datetime is in UTC
        dt_type: pl.Datetime = processed_data["datetime"].dtype  # type: ignore
        if dt_type.time_zone != str(dt.timezone.utc):
            raise WeatherAPIError(
                f"Datetime column is not in UTC, is {dt_type.time_zone}."
            )

        # check for gaps and NaN values
        if not all(processed_data["datetime"].diff()[1:] == self.freq_source):
            raise WeatherAPIError("Processed data contains gaps.")
        if any(col.has_validity() for col in processed_data):
            raise WeatherAPIError("Processed data contains NaN values.")

        # cut off the data that exceeds max_forecast_days
        processed_data = processed_data.filter(pl.col("datetime") <= self.end_forecast)

        # set data types
        processed_data = processed_data.cast(
            {
                "cloud_coverage": pl.Float64,
                "humidity": pl.Int64,
                "temperature": pl.Float64,
                "wind_speed": pl.Float64,
            }
        )

        # calculate irradiance from cloud cover
        if calc_irrads:
            _LOGGER.debug("Calculating irradiance from cloud cover.")
            irrads = self.cloud_cover_to_irradiance(
                processed_data["cloud_coverage"].to_frame()
            )
            processed_data = pl.concat([processed_data, irrads], how="horizontal")

        # convert datetime column to str
        processed_data = processed_data.with_columns(
            processed_data["datetime"].dt.strftime("%Y-%m-%dT%H:%M:%S%z")
        )

        # convert to dictionary and validate schema
        data_dict = processed_data.to_dict(as_series=False)
        data_list = [dict(zip(data_dict, t)) for t in zip(*data_dict.values())]
        try:
            validated_data = {
                "source": self.__class__.__name__,
                "interval": timedelta_to_pl_duration(self.freq_source),
                "data": data_list,
            }
            WEATHER_SCHEMA(validated_data)
        except Exception as exc:
            raise WeatherAPIError(
                f"Error validating weather data: {validated_data}"
            ) from exc

        # cache data
        self._weather_data = validated_data
        return validated_data

    def cloud_cover_to_irradiance(
        self, cloud_cover: pl.DataFrame, how: str = "clearsky_scaling", **kwargs: Any
    ) -> pl.DataFrame:
        """
        Convert cloud cover to irradiance. A wrapper method.

        NB: Code copied from pvlib.forecast as the pvlib forecast module is deprecated as of pvlib 0.9.1!

        :param cloud_cover: Cloud cover as a polars pl.Series
        :param how: Selects the method for conversion. Can be one of clearsky_scaling or campbell_norman.
        :param **kwargs: Passed to the selected method.
        :return: Irradiance, columns include ghi, dni, dhi.
        """
        # datetimes must be provided as a pd.DatetimeIndex otherwise pvlib fails
        times = pd.date_range(
            cloud_cover["datetime"].min(),
            cloud_cover["datetime"].max(),
            freq=self.freq_source,
        )

        # convert cloud cover to GHI/DNI/DHI
        how = how.lower()
        if how == "clearsky_scaling":
            irrads = self._cloud_cover_to_irradiance_clearsky_scaling(
                cloud_cover, times, **kwargs
            )
        elif how == "campbell_norman":
            irrads = self._cloud_cover_to_irradiance_campbell_norman(
                cloud_cover, times, **kwargs
            )
        else:
            raise ValueError(f"Invalid how argument: {how}")
        _LOGGER.debug(
            "Converted cloud cover to irradiance using %s. Result: \n%s", how, irrads
        )
        return irrads

    def _cloud_cover_to_irradiance_clearsky_scaling(
        self, cloud_cover: pl.DataFrame, times: pd.DatetimeIndex, **kwargs: Any
    ) -> pl.DataFrame:
        """
        Convert cloud cover to irradiance using the clearsky scaling method.

        :param cloud_cover: Cloud cover as a polars pl.Series
        :param **kwargs: Passed to the selected method.
        :return: Irradiance, columns include ghi, dni, dhi.
        """
        # get clear sky data for provided datetimes
        solpos = self.location.get_solarposition(times)
        clear_sky = self.location.get_clearsky(times, "ineichen", solpos)
        cover = pl.Series.to_pandas(cloud_cover["cloud_cover"])

        # convert cloud cover to GHI/DNI/DHI
        ghi = self._cloud_cover_to_ghi_linear(
            cover.to_numpy(), clear_sky["ghi"].to_numpy(), **kwargs
        )

        dni = disc(ghi, solpos["zenith"], times)["dni"]
        dhi = ghi - dni * np.cos(np.radians(solpos["zenith"]))

        # construct df with ghi, dni, dhi and fill NaNs with 0
        return (
            pl.DataFrame({"ghi": ghi, "dni": dni, "dhi": dhi}).fill_null(0).fill_nan(0)
        )

    def _cloud_cover_to_irradiance_campbell_norman(
        self, cloud_cover: pl.DataFrame, times: pd.DatetimeIndex, **kwargs: Any
    ) -> pl.DataFrame:
        """
        Convert cloud cover to irradiance using the Campbell and Norman model.

        :param cloud_cover: Cloud cover in [%] as a polars pl.DataFrame.
        :param **kwargs: Passed to the selected method.
        :return: Irradiance as a polars pl.DataFrame with columns ghi, dni, dhi.
        """
        # get clear sky data for provided datetimes
        zen = self.location.get_solarposition(times)["apparent_zenith"].to_numpy()
        dni_extra = get_extra_radiation(times).to_numpy()
        transmittance = self._cloud_cover_to_transmittance_linear(
            cloud_cover["cloud_cover"].to_numpy(), **kwargs
        )

        # convert cloud cover to GHI/DNI/DHI
        irrads = campbell_norman(zen, transmittance, dni_extra=dni_extra)

        # construct df with ghi, dni, dhi and fill NaNs with 0
        return (
            pl.DataFrame(
                {"ghi": irrads["ghi"], "dni": irrads["dni"], "dhi": irrads["dhi"]}
            )
            .fill_null(0)
            .fill_nan(0)
        )

    def _cloud_cover_to_transmittance_linear(
        self, cloud_cover: np.ndarray[float, Any], offset: float = 0.75
    ) -> np.ndarray[float, Any]:
        """
        Convert cloud cover (percentage) to atmospheric transmittance
        using a linear model.

        :param cloud_cover: Cloud cover in [%] as a polars pl.Series.
        :param offset: Determines the maximum transmittance for the linear model.
        :return: Atmospheric transmittance as a polars pl.Series.
        """
        return ((100.0 - cloud_cover) / 100.0) * offset

    def _cloud_cover_to_ghi_linear(
        self,
        cloud_cover: np.ndarray[float, Any],
        ghi_clear: np.ndarray[float, Any],
        offset: float = 35.0,
    ) -> np.ndarray[float, Any]:
        """
        Convert cloud cover to GHI using a linear relationship.

        :param cloud_cover: Cloud cover in [%] as a pandas pd.Series.
        :param ghi_clear: Clear sky GHI as a pandas pd.Series.
        :param offset: Determines the maximum GHI for the linear model.
        :return: GHI as a numpy array.
        """
        offset = offset / 100.0
        cloud_cover = cloud_cover / 100.0
        ghi = (offset + (1 - offset) * (1 - cloud_cover)) * ghi_clear
        return np.array(ghi, dtype=np.float64)


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
    def from_date(cls, date: Union[str, dt.datetime]) -> WeatherAPIErrorNoData:
        """Create an exception for a specific date.

        :param date: The date for which no weather data is available.
        :return: The exception.
        """
        return cls(f"No weather data available for {date}")


@dataclass(frozen=True)
class WeatherAPIErrorTimeout(WeatherAPIError):
    """Exception error 408, timeout."""

    message: str = field(default="API timeout")
    error: int = field(default=408)


@dataclass(frozen=True)
class WeatherAPIErrorNoLocation(WeatherAPIError):
    """No data for location available."""

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
