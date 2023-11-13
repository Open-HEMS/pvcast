"""Weather API class that scrapes the data from Clear Outside."""

from __future__ import annotations

import logging
from dataclasses import InitVar, dataclass, field
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup

from ..weather.weather import WeatherAPI

_LOGGER = logging.getLogger(__name__)


@dataclass
class WeatherAPIClearOutside(WeatherAPI):
    """Weather API class that scrapes the data from Clear Outside."""

    sourcetype: str = field(default="clearoutside")
    url: str = field(init=False)
    _url_base: InitVar[str] = field(default="https://clearoutside.com/forecast/")
    _columns: list[str] = field(default_factory=list)

    def __post_init__(self, _url_base: str) -> None:
        self.url = self._url_formatter(_url_base)
        self._columns = ["cloud_coverage", "wind_speed", "temperature", "humidity"]

    def _url_formatter(self, url_base: str) -> str:
        """Format the url to the API."""

        def encode(coord: float) -> str:
            return str(round(coord, 2))

        lat = encode(self.location.latitude)
        lon = encode(self.location.longitude)
        alt = encode(self.location.altitude)
        return urljoin(url_base, f"{lat}/{lon}/{alt}")

    def _process_data(self) -> pd.DataFrame:
        """Process weather data scraped from the clear outside website.

        Credits to https://github.com/davidusb-geek/emhass for the parsing code.

        This function takes no arguments, but response.content must be retrieved from self._raw_data.
        """
        # raw response data from request
        if not self._raw_data:
            raise ValueError("Field self._raw_data not set, run self.get_data() first.")
        response = self._raw_data

        # response (source) data bucket
        weather_df = pd.DataFrame(index=self.source_dates, columns=self._columns)

        # parse the data
        n_days = int(self.max_forecast_days / pd.Timedelta(days=1))
        for day_int in range(n_days):
            result = BeautifulSoup(response.content, "html.parser").find_all(
                id=f"day_{day_int}"
            )
            if len(result) != 1:
                _LOGGER.warning("No data for day %s.", day_int)
                break

            table = result[0]

            # find the elements in the table
            data = self._find_elements(table)

            # insert the data into the source data bucket
            weather_df.iloc[day_int * 24 : (day_int + 1) * 24] = data

        # check that all rows with NaN are at the end of the data
        rows_with_nan = weather_df.isna().any(axis=1)
        if not rows_with_nan.sum() == 0:
            _LOGGER.debug("Dropping %s rows with NaN.", rows_with_nan.sum())
            if not weather_df.isna().any(axis=1).diff().sum() == 1:
                _LOGGER.warning("Found NaN in the middle of the data.")
                weather_df.interpolate(
                    method="linear", inplace=True, limit_area="inside"
                )
            weather_df.dropna(inplace=True)

        return weather_df

    def _find_elements(self, table: BeautifulSoup) -> pd.DataFrame:
        """Find weather data elements in the table.

        :param table: The table to search.
        :return: Weather data pd.DataFrame for one day (24 hours).
        """

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

        # select subset of columns
        raw_data = raw_data[
            [
                "Total Clouds (% Sky Obscured)",
                "Wind Speed/Direction (mph)",
                "Temperature (°C)",
                "Relative Humidity (%)",
            ]
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
