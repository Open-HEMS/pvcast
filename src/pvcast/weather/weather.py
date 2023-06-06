"""Read weather forecast data and put it into a format that can be used by the pvcast module."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup

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


@dataclass(frozen=True)
class WeatherAPIClearOutside(WeatherAPI):
    """Weather API class that scrapes the data from Clear Outside."""

    url_base: str = field(default="https://clearoutside.com/forecast/")

    def _do_api_request(self) -> requests.Response:
        """Do a request to the API and store the response in self._response.

        :return: The API data.
        """
        # get the data from clear outside
        if self.format_url:
            url = f"{self.url_base}{str(round(self.lat, 2))}/{str(round(self.lon, 2))}/{str(round(self.alt, 2))}"
        else:
            url = self.url_base

        # do the request
        try:
            response = requests.get(url, timeout=10)
        except requests.exceptions.Timeout as exc:
            raise WeatherAPIErrorTimeout() from exc

        # response handling
        self.api_error_handler(response)

        # return the response
        return response

    def get_weather(self) -> dict:
        """Get weather data from the API.

        Credits to https://github.com/davidusb-geek/emhass for the parsing code.

        :return: The weather data as a dataframe where the index is the datetime and the columns are the variables.
        """
        # do the request
        response = self._do_api_request()

        # parse the data
        try:
            table = BeautifulSoup(response.content, "html.parser").find_all(id="day_0")[0]
        except IndexError as exc:
            raise WeatherAPIErrorNoData.from_date(self.start_forecast.strftime("%Y-%m-%d")) from exc

        list_names = table.find_all(class_="fc_detail_label")
        list_tables = table.find_all("ul")[1:]

        # selected variables
        sel_cols = [0, 1, 2, 3, 10, 12, 15]
        col_names = [list_names[i].get_text() for i in sel_cols]
        list_tables = [list_tables[i] for i in sel_cols]

        # building the raw DF container
        raw_data = pd.DataFrame(index=range(24), columns=col_names, dtype=float)
        for count_col, col in enumerate(col_names):
            list_rows = list_tables[count_col].find_all("li")
            for count_row, row in enumerate(list_rows):
                raw_data.loc[count_row, col] = float(row.get_text())

        # treating index
        freq_scrap = pd.to_timedelta(60, "minutes")
        forecast_dates_scrap = pd.date_range(
            start=self.start_forecast, end=self.end_forecast - freq_scrap, freq=freq_scrap
        )

        # interpolating and reindexing
        raw_data.set_index(forecast_dates_scrap, inplace=True)
        raw_data.drop_duplicates(inplace=True)
        raw_data = raw_data.reindex(self.forecast_dates)
        raw_data.interpolate(method="linear", axis=0, limit=None, limit_direction="both", inplace=True)

        # select subset of columns
        raw_data = raw_data[
            ["Total Clouds (% Sky Obscured)", "Wind Speed/Direction (mph)", "Temperature (°C)", "Relative Humidity (%)"]
        ]

        # rename columns
        raw_data.rename(
            columns={
                "Total Clouds (% Sky Obscured)": "cloud_cover",
                "Wind Speed/Direction (mph)": "wind_speed",
                "Temperature (°C)": "temperature",
                "Relative Humidity (%)": "humidity",
            },
            inplace=True,
        )

        # convert wind speed to m/s
        raw_data["wind_speed"] = raw_data["wind_speed"] * 0.44704

        return raw_data
