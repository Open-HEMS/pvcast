"""Read weather forecast data and put it into a format that can be used by the pvcast module."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd
import requests
from pvlib.irradiance import campbell_norman, disc, get_extra_radiation
from pvlib.location import Location
from requests import Response
from voluptuous import All, Datetime, In, Optional, Range, Required, Schema

_LOGGER = logging.getLogger(__name__)

# schema for weather data
WEATHER_SCHEMA = Schema(
    {
        Required("source"): str,
        Required("frequency"): In(["15Min", "30Min", "1H", "1D", "1W", "M", "Y"]),
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

# temperature conversion functions ("°C", "°F", "C", "F")
TEMP_CONV_DICT = {
    "F": {
        "C": lambda x: (5 / 9) * (x - 32),
    },
    "C": {
        "C": lambda x: x,
    },
}

# speed conversion functions ("m/s", "km/h", "mi/h", "ft/s", "kn")
SPEED_CONV_DICT = {
    "m/s": {
        "km/h": lambda x: x * 3.6,
    },
    "km/h": {
        "m/s": lambda x: x / 3.6,
    },
    "mi/h": {
        "m/s": lambda x: x / 2.23694,
    },
    "ft/s": {
        "m/s": lambda x: x / 3.28084,
    },
    "kn": {
        "m/s": lambda x: x / 1.94384,
    },
}

# combine temperature and speed conversion dictionaries
CONV_DICT = {**TEMP_CONV_DICT, **SPEED_CONV_DICT}


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

    # timeout in seconds for the API request
    timeout: int = field(default=10)

    # maximum number of days to include in the forecast
    max_forecast_days: pd.Timedelta = field(default=pd.Timedelta(days=7))

    # frequency of the source data and the output data
    freq_source: str = field(
        default="1H"
    )  # frequency of the source data. This is fixed!
    freq_output: str = field(
        default="1H"
    )  # frequency of the output data. Can be changed by user.

    # maximum age of weather data before requesting new data
    max_age: pd.Timedelta = field(default=pd.Timedelta(hours=1))
    _last_update: pd.Timestamp = field(
        default=pd.Timestamp(0, tz="UTC"), init=False
    )  # last time the weather data was updated

    # raw response data from the API
    _raw_data: Response = field(default=None, init=False)

    @property
    def start_forecast(self) -> pd.Timestamp:
        """Get the start date of the forecast."""
        return pd.Timestamp.utcnow().floor("1H")

    @property
    def end_forecast(self) -> pd.Timestamp:
        """Get the end date of the forecast."""
        return (
            self.start_forecast
            + self.max_forecast_days
            - pd.Timedelta(self.freq_source)
        )

    @property
    def source_dates(self) -> pd.DatetimeIndex:
        """
        Get the pd.DatetimeIndex to store the forecast. These are only used if missing from API, the weather API can
        also return datetime strings and in that case this index is not needed and even not preferred.
        """
        return self.get_source_dates(
            self.start_forecast, self.end_forecast, self.freq_source
        )

    @staticmethod
    def get_source_dates(
        start: pd.Timestamp | datetime, end: pd.Timestamp | datetime, freq: str
    ) -> pd.DatetimeIndex:
        """
        Get the pd.DatetimeIndex to store the forecast. These are only used if missing from API, the weather API can
        also return datetime strings and in that case this index is not needed and even not preferred.
        """
        start = pd.Timestamp(start)
        end = pd.Timestamp(end)
        # floor start, end to freq and return DatetimeIndex
        return pd.date_range(start.floor("1H"), end.floor("1H"), freq=freq, tz="UTC")

    @staticmethod
    def convert_unit(data: pd.Series, from_unit: str, to_unit: str) -> pd.Series:
        """Convert units of a pd.Series.

        :param data: The data to convert. This should be a pd.Series.
        :param to_unit: The unit to convert to.
        :return: Data with applied unit conversion.
        """
        if not isinstance(data, pd.Series):
            raise TypeError("Data must be a pd.Series.")

        # remove degree symbol from units if present
        from_unit = from_unit.replace("°", "")
        to_unit = to_unit.replace("°", "")

        if from_unit not in CONV_DICT:
            raise ValueError(f"Conversion from unit [{from_unit}] not supported.")
        if from_unit == to_unit:
            return data
        if to_unit not in CONV_DICT[from_unit]:
            raise ValueError(
                f"Conversion from [{from_unit}] to [{to_unit}] not supported."
            )

        # do unit conversion
        return data.apply(CONV_DICT[from_unit][to_unit])

    @abstractmethod
    def _process_data(self) -> pd.DataFrame:
        """Process data from the weather API.

        The index of the returned pd.DataFrame should be a pd.DatetimeIndex in local time.

        :return: The weather data as a pd.DataFrame where the index is the datetime and the columns are the variables.
        """

    def get_weather(self, live: bool = False, calc_irrads: bool = False) -> dict:
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
        processed_data: pd.DataFrame = self._process_data()

        if processed_data.index.freq is None:
            raise WeatherAPIError("Processed data does not have a known frequency.")
        if processed_data.index.freq != self.freq_source:
            raise WeatherAPIError(
                f"Data freq ({processed_data.index.freq}) != source freq ({self.freq_source})."
            )

        # cut off the data that exceeds either max_forecast_days or int(number of days in the source data)
        n_days_data = (processed_data.index[-1] - processed_data.index[0]).days + 1
        n_days = int(min(n_days_data, self.max_forecast_days.days))
        processed_data = processed_data.iloc[
            : n_days * (pd.Timedelta(hours=24) // pd.Timedelta(self.freq_source))
        ]

        # check for NaN values
        if pd.isnull(processed_data).any().any():
            raise WeatherAPIError("Processed data contains NaN values.")

        # set data types
        data_type_dict = {
            "temperature": float,
            "humidity": int,
            "wind_speed": float,
            "cloud_coverage": int,
        }
        processed_data = processed_data.astype(data_type_dict)

        # resample to the output frequency and interpolate
        if self.freq_output != self.freq_source:
            processed_data = (
                processed_data.resample(self.freq_output)
                .interpolate(method="linear")
                .iloc[:-1]
            )

        resampled = processed_data.tz_convert("UTC")
        resampled["datetime"] = resampled.index.strftime("%Y-%m-%dT%H:%M:%S%z")

        # set data types again after resampling
        resampled = resampled.astype(data_type_dict)

        # calculate irradiance from cloud cover
        if calc_irrads:
            irrads = self.cloud_cover_to_irradiance(resampled["cloud_coverage"])
            resampled["ghi"] = irrads["ghi"]
            resampled["dni"] = irrads["dni"]
            resampled["dhi"] = irrads["dhi"]

        # convert to dictionary and validate schema
        try:
            data_dict = {
                "source": self.__class__.__name__,
                "frequency": self.freq_output,
                "data": resampled.to_dict(orient="records"),
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
        delta_t = pd.Timestamp.now(tz="UTC") - self._last_update
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
        self._last_update = pd.Timestamp.now(tz="UTC")
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
                raise WeatherAPIError(response.status_code)

    def cloud_cover_to_irradiance(
        self, cloud_cover: pd.Series, how: str = "clearsky_scaling", **kwargs
    ):
        """
        Convert cloud cover to irradiance. A wrapper method.

        NB: Code copied from pvlib.forecast as the pvlib forecast module is deprecated as of pvlib 0.9.1!

        :param cloud_cover: Cloud cover as a pandas pd.Series
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
        self, cloud_cover: pd.Series, method="linear", **kwargs
    ):
        """
        Convert cloud cover to irradiance using the clearsky scaling method.

        :param cloud_cover: Cloud cover as a pandas pd.Series
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

        irrads = pd.DataFrame({"ghi": ghi, "dni": dni, "dhi": dhi}).fillna(0)
        return irrads

    def _cloud_cover_to_irradiance_campbell_norman(
        self, cloud_cover: pd.Series, **kwargs
    ):
        """
        Convert cloud cover to irradiance using the Campbell and Norman model.

        :param cloud_cover: Cloud cover in [%] as a pandas pd.Series.
        :param **kwargs: Passed to the selected method.
        :return: Irradiance as a pandas pd.DataFrame with columns ghi, dni, dhi.
        """
        solar_position = self.location.get_solarposition(cloud_cover.index)
        dni_extra = get_extra_radiation(cloud_cover.index)

        transmittance = self.cloud_cover_to_transmittance_linear(cloud_cover, **kwargs)

        irrads = campbell_norman(
            solar_position["apparent_zenith"], transmittance, dni_extra=dni_extra
        )
        irrads = irrads.fillna(0)

        return irrads

    def _cloud_cover_to_ghi_linear(
        self, cloud_cover: pd.Series, ghi_clear: pd.Series, offset: float = 35.0
    ):
        """
        Convert cloud cover to GHI using a linear relationship.

        :param cloud_cover: Cloud cover in [%] as a pandas pd.Series.
        :param ghi_clear: Clear sky GHI as a pandas pd.Series.
        :param offset: Determines the maximum GHI for the linear model.
        :return: GHI as a pandas pd.Series.
        """
        offset = offset / 100.0
        cloud_cover = cloud_cover / 100.0
        ghi = (offset + (1 - offset) * (1 - cloud_cover)) * ghi_clear
        return ghi

    def cloud_cover_to_transmittance_linear(
        self, cloud_cover: pd.Series, offset: float = 0.75
    ):
        """
        Convert cloud cover (percentage) to atmospheric transmittance
        using a linear model.

        :param cloud_cover: Cloud cover in [%] as a pandas pd.Series.
        :param offset: Determines the maximum transmittance for the linear model.
        :return: Atmospheric transmittance as a pandas pd.Series.
        """
        return ((100.0 - cloud_cover) / 100.0) * offset

    def _add_freq(self, idx: pd.DatetimeIndex, freq=None) -> pd.DatetimeIndex:
        """Add a frequency attribute to idx, through inference or directly.

        Returns a copy.  If `freq` is None, it is inferred.

        :param idx: pd.DatetimeIndex to add frequency to.
        :param freq: Frequency to add to idx.
        :return: pd.DatetimeIndex with frequency attribute.
        """
        idx = idx.copy()
        if freq is None:
            if idx.freq is None:
                freq = pd.infer_freq(idx)
            else:
                return idx
        idx.freq = pd.tseries.frequencies.to_offset(freq)
        if idx.freq is None:
            raise AttributeError(
                "no discernible frequency found to `idx`.  Specify a frequency string with `freq`."
            )
        return idx


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

    def get_weather_api_list_obj(self) -> list[WeatherAPI]:
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