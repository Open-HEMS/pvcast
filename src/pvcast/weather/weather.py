"""Read weather forecast data and put it into a format that can be used by the pvcast module."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Tuple

import requests
from bs4 import BeautifulSoup
import pandas as pd

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class WeatherAPI(ABC):
    """Abstract WeatherAPI class."""

    # require lat, lon to have at least 2 decimal places of precision
    lat: float
    lon: float
    alt: float

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
    def get_weather(self) -> dict:
        """Get weather data from the API.

        :return: The weather data as a dictionary where the format is: {"date": {"variable": value}}.
        """


@dataclass(frozen=True)
class WeatherAPIError(Exception):
    """Exception class for weather API errors."""

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
class WeatherAPIErrorNoLocation(WeatherAPIError):
    """Exception class for weather API errors."""

    message: str = field(default="No data for location available")


@dataclass(frozen=True)
class WeatherAPIClearOutside(WeatherAPI):
    """Weather API class that scrapes the data from Clear Outside."""

    url_base: str = field(default="https://clearoutside.com/forecast/")

    def get_weather(self) -> dict:
        """Get weather data from the API.

        Credits to https://github.com/davidusb-geek/emhass for the parsing code.

        :return: The weather data as a dictionary where the format is: {"date": {"variable": value}}.
        """
        # Get the data from website
        response = requests.get(
            f"{self.url_base}{str(round(self.lat, 2))}/{str(round(self.lon, 2))}?desktop=true", timeout=10
        )
        if response.status_code != 200:
            raise WeatherAPIError(f"Error while retrieving data from {self.url_base}")

        table = BeautifulSoup(response.content, "html.parser").find_all(id="day_0")[0]
        list_names = table.find_all(class_="fc_detail_label")
        list_tables = table.find_all("ul")[1:]

        # Selected variables
        sel_cols = [0, 1, 2, 3, 10, 12, 15]
        col_names = [list_names[i].get_text() for i in sel_cols]
        list_tables = [list_tables[i] for i in sel_cols]

        # Building the raw DF container
        raw_data = pd.DataFrame(index=range(24), columns=col_names, dtype=float)
        for count_col, col in enumerate(col_names):
            list_rows = list_tables[count_col].find_all("li")
            for count_row, row in enumerate(list_rows):
                raw_data.loc[count_row, col] = float(row.get_text())

        # Treating index
        freq_scrap = pd.to_timedelta(60, "minutes")
        forecast_dates_scrap = pd.date_range(
            start=self.start_forecast, end=self.end_forecast - freq_scrap, freq=freq_scrap
        )

        raw_data.set_index(forecast_dates_scrap, inplace=True)
        raw_data.drop_duplicates(inplace=True)
        raw_data = raw_data.reindex(self.forecast_dates)
        raw_data.interpolate(method="linear", axis=0, limit=None, limit_direction="both", inplace=True)

        # Converting to dict
        return raw_data.to_dict(orient="index")
