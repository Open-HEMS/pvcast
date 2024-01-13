"""Weather API class that scrapes the data from Clear Outside."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import InitVar, dataclass, field
from urllib.parse import urljoin

import polars as pl
import requests
from bs4 import BeautifulSoup

from ..weather.weather import WeatherAPI, WeatherAPIErrorTimeout

_LOGGER = logging.getLogger(__name__)


@dataclass
class WeatherAPIClearOutside(WeatherAPI):
    """Weather API class that scrapes the data from Clear Outside."""

    sourcetype: str = field(default="clearoutside")
    url: str = field(init=False)
    _url_base: InitVar[str] = field(default="https://clearoutside.com/forecast/")

    def __post_init__(self, _url_base: str) -> None:
        lat = str(round(self.location.latitude, 2))
        lon = str(round(self.location.longitude, 2))
        alt = str(round(self.location.altitude, 2))
        self.url = urljoin(_url_base, f"{lat}/{lon}/{alt}")

    def retrieve_new_data(self) -> pl.DataFrame:
        """Retrieve weather data by scraping it from the clear outside website."""
        try:
            response = requests.get(self.url, timeout=int(self.timeout.total_seconds()))
        except requests.exceptions.Timeout as exc:
            raise WeatherAPIErrorTimeout() from exc

        # response (source) data bucket
        weather_df = pl.DataFrame()

        n_days = int(self.max_forecast_days / dt.timedelta(days=1))

        # Parse HTML content once
        soup = BeautifulSoup(response.content, "lxml")

        for day_int in range(n_days):
            # find the table for the day
            result = soup.select(f"#day_{day_int}")
            if len(result) != 1:
                _LOGGER.debug("No data for day %s, breaking loop.", day_int)
                break

            # find the elements in the table
            table = result[0]
            data = self._find_elements(table)

            # insert the data into the source data bucket
            weather_df = weather_df.vstack(data.with_columns(pl.all().cast(pl.Float64)))

        # add the datetime column
        weather_df = weather_df.with_columns(
            self.source_dates.slice(0, len(weather_df)).alias("datetime")
        )

        # check NaN values distribution
        nan_vals = weather_df.with_columns(pl.all().is_null().cast(int).diff().sum())
        if any(col.item() > 1 for col in nan_vals[0]):
            raise ValueError(f"Found more than one intermediate NaN value: {nan_vals}")

        # interpolate NaN values
        weather_df = weather_df.interpolate()
        weather_df = weather_df.drop_nulls()
        return weather_df

    def _find_elements(self, table: BeautifulSoup) -> pl.DataFrame:
        """Find weather data elements in the table.

        :param table: The table to search.
        :return: Weather data pl.DataFrame for one day (24 hours).
        """

        list_names = table.find_all(class_="fc_detail_label")
        list_tables = table.find_all("ul")[1:]

        # selected variables
        sel_cols = [0, 1, 2, 3, 10, 12, 15]
        col_names = [list_names[i].get_text() for i in sel_cols]
        list_tables = [list_tables[i] for i in sel_cols]

        # building the raw DF container
        raw_data = pl.DataFrame({"index": range(24)})
        for count_col, col in enumerate(col_names):
            list_rows = list_tables[count_col].find_all("li")

            # create empty column and fill it with data up len(column_data)
            column_data = pl.Series(col, [float(row.get_text()) for row in list_rows])
            raw_data = pl.concat([raw_data, column_data.to_frame()], how="horizontal")

        # rename columns
        raw_data = raw_data.select(
            pl.col("Total Clouds (% Sky Obscured)").alias("cloud_cover"),
            pl.col("Wind Speed/Direction (mph)").alias("wind_speed"),
            pl.col("Temperature (°C)").alias("temperature"),
            pl.col("Relative Humidity (%)").alias("humidity"),
        )

        # convert wind speed to m/s
        raw_data = raw_data.with_columns(pl.col("wind_speed") * 0.44704)
        return raw_data
