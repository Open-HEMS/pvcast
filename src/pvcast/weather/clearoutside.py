"""Weather API class that scrapes the data from Clear Outside."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd
from bs4 import BeautifulSoup
from pandas import DataFrame, Timedelta

from ..weather.weather import WeatherAPI

_LOGGER = logging.getLogger(__name__)


@dataclass()
class WeatherAPIClearOutside(WeatherAPI):
    """Weather API class that scrapes the data from Clear Outside."""

    _url_base: str = field(default="https://clearoutside.com/forecast/")

    def _url_formatter(self) -> str:
        """Format the url to the API."""

        def encode(coord: float) -> str:
            return str(round(coord, 2))

        lat = encode(self.location.latitude)
        lon = encode(self.location.longitude)
        alt = encode(self.location.altitude)
        return f"{self._url_base}{lat}/{lon}/{alt}"

    def _process_data(self) -> DataFrame:
        """Process weather data scraped from the clear outside website.

        Credits to https://github.com/davidusb-geek/emhass for the parsing code.

        This function takes no arguments, but response.content must be retrieved from self._raw_data.
        """
        # raw response data from request
        response = self._raw_data

        # response (source) data bucket
        source_df = DataFrame(index=self.source_dates)

        # parse the data
        n_days = int(self.max_forecast_days / Timedelta(days=1))
        for day_int in range(n_days):
            table = BeautifulSoup(response.content, "html.parser").find_all(id=f"day_{day_int}")[0]
            if table is None:
                _LOGGER.warning("No table found for day %s.", day_int)
                break

            # find the elements in the table
            data = self._find_elements(table, day_int)
            if data.isna().values.all(axis=0).all():
                _LOGGER.warning("All data NaN for day %s.", day_int)
                break

            # insert the data into the source data bucket
            source_df.loc[data.index, data.columns] = data

        # return the source data bucket
        return source_df

    def _find_elements(self, table: list, day: int) -> DataFrame:
        """Find weather data elements in the table.

        :param table: The table to search.
        :param day: The day of the table.
        :return: Weather data dataframe for one day (24 hours).
        """

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
        freq_scrap = pd.Timedelta(self.freq_source)
        start_forecast = self.start_forecast + Timedelta(days=1) * day
        end_forecast = self.start_forecast + Timedelta(days=1) * (day + 1)
        forecast_dates_scrap = pd.date_range(start=start_forecast, end=end_forecast - freq_scrap, freq=freq_scrap)

        # interpolating and reindexing
        raw_data.set_index(forecast_dates_scrap, inplace=True)
        raw_data.drop_duplicates(inplace=True)

        # select subset of columns
        raw_data = raw_data[
            ["Total Clouds (% Sky Obscured)", "Wind Speed/Direction (mph)", "Temperature (°C)", "Relative Humidity (%)"]
        ]

        # rename columns
        raw_data.rename(
            columns={
                "Total Clouds (% Sky Obscured)": "cloud_coverage",
                "Wind Speed/Direction (mph)": "wind_speed",
                "Temperature (°C)": "temperature",
                "Relative Humidity (%)": "humidity",
            },
            inplace=True,
        )

        # convert wind speed to m/s
        raw_data["wind_speed"] = raw_data["wind_speed"] * 0.44704
        return raw_data
