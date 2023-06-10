"""Weather API class that scrapes the data from Clear Outside."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd
import requests
from bs4 import BeautifulSoup
from pandas import DataFrame, Timedelta, Timestamp

from pvcast.weather.weather import (WeatherAPI, WeatherAPIErrorNoData,
                                    WeatherAPIErrorTimeout)

_LOGGER = logging.getLogger(__name__)


@dataclass()
class WeatherAPIClearOutside(WeatherAPI):
    """Weather API class that scrapes the data from Clear Outside."""

    _url_base: str = field(default="https://clearoutside.com/forecast/")

    def _url_formatter(self) -> str:
        """Format the url to the API."""
        return f"{self._url_base}{str(round(self.lat, 2))}/{str(round(self.lon, 2))}/{str(round(self.alt, 2))}"

    def _process_data(self, response: requests.Response) -> DataFrame:
        """Process weather data scraped from the clear outside website.

        Credits to https://github.com/davidusb-geek/emhass for the parsing code.

        :return: The weather data as a dataframe where the index is the datetime and the columns are the variables.
        """

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
        raw_data = DataFrame(index=range(24), columns=col_names, dtype=float)
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
