"""Model based PV power forecasting."""

from __future__ import annotations

import copy
import datetime as dt
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import polars as pl
from pvlib.atmosphere import gueymard94_pw
from pvlib.iotools import get_pvgis_tmy
from pvlib.location import Location

from .const import (
    HISTORICAL_YEAR_MAPPING,
    SECONDS_PER_HOUR,
    VALID_DOWN_SAMPLE_FREQ,
    VALID_UPSAMPLE_FREQ,
)

if TYPE_CHECKING:
    from .model import PVPlantModel


_LOGGER = logging.getLogger(__name__)


class ForecastType(str, Enum):
    """Enum for the type of PVPlantResults."""

    LIVE = "live"
    CLEARSKY = "clearsky"
    HISTORICAL = "historic"


@dataclass
class ForecastResult:
    """Object to store the aggregated results of the PVPlantModel simulation.

    :param name: The name of the PV plant.
    :param type: The type of the result: forecast based on live weather data, clearsky, or historic based on PVGIS TMY.
    :param ac_power: The sum of AC power outputs of all ModelChain objects in the PV plant.
    :param freq: Frequency of original data. Can be "1H" for hourly, "1D" for daily, "M" for monthly, "A" for yearly.
    """

    name: str
    type: ForecastType
    ac_power: pl.DataFrame | None = field(repr=False, default=None)

    def __post_init__(self) -> None:
        if self.ac_power is None:
            raise ValueError("Must provide AC power data.")
        if "datetime" not in self.ac_power.columns:
            raise ValueError("AC power data must have a 'datetime' column.")
        if self.ac_power["datetime"].dtype != pl.Datetime:
            raise ValueError(
                f"Datetime column must have dtype datetime.datetime. Got {self.ac_power['datetime'].dtype}."
            )
        if self.ac_power.null_count().sum_horizontal().item() > 0:
            raise ValueError("AC power data contains null values.")
        if "ac_power" not in self.ac_power.columns:
            raise ValueError("AC power data must have a 'ac_power' column.")
        if self.ac_power["ac_power"].dtype != pl.Int64:
            raise ValueError(
                f"AC power column must have dtype int64. Got {self.ac_power['ac_power'].dtype}."
            )

    def upsample(self, freq: str) -> ForecastResult:
        """Resample the ForecastResult to a new interval, apply linear interpolation and
        return a new ForecastResult object.

        :param freq: The frequency of the energy output. See polars.upsample() for valid options.
        :return: A new ForecastResult object with the resampled data.
        """
        if freq not in VALID_UPSAMPLE_FREQ:
            raise ValueError(
                f"Invalid frequency. Must be one of {VALID_UPSAMPLE_FREQ}."
            )
        if self.ac_power is None:
            raise ValueError("No AC power data available. Run simulation first.")

        # copy the ForecastResult object
        fc_result_cpy = copy.deepcopy(self)
        current_freq: int = fc_result_cpy.frequency
        target_freq: int = fc_result_cpy._time_str_to_seconds(freq)

        if current_freq < target_freq:
            raise ValueError(
                f"Cannot upsample to a lower frequency. Current frequency is {fc_result_cpy.frequency}s."
            )
        if current_freq == target_freq:
            return fc_result_cpy

        # upsample the data
        fc_result_cpy.ac_power = (
            fc_result_cpy.ac_power.sort(by="datetime")  # type: ignore
            .upsample(time_column="datetime", every=freq, maintain_order=True)
            .select(pl.all().forward_fill())
        )
        return fc_result_cpy

    @property
    def frequency(self) -> int:
        """Return the frequency of the data in seconds.
        NB: This is actually the data interval, not the frequency.
        """
        if self.ac_power is None:
            _LOGGER.warning("No AC power data available. Run simulation first.")
            return 0
        # check if time series data is equidistantly spaced in time
        if not self.ac_power["datetime"].is_sorted():
            raise ValueError("Datetime column must be sorted.")
        intervals = self.ac_power["datetime"].diff()[1:].unique()

        # check if intervals are equidistantly spaced in time.
        # first value of diff() is NaN, hence we need two unique values
        if not intervals.diff().n_unique() == 2:
            raise ValueError("Datetime column must be equidistantly spaced in time.")

        interval: dt.timedelta = intervals.item()
        return int(interval.seconds)

    def _time_str_to_seconds(self, time_str: str) -> int:
        """Convert a time string to seconds."""
        if time_str.endswith("s"):
            return int(time_str[:-1])
        if time_str.endswith("m"):
            return int(time_str[:-1]) * 60
        if time_str.endswith("h"):
            return int(time_str[:-1]) * 60 * 60
        if time_str.endswith("d"):
            return int(time_str[:-1]) * 60 * 60 * 24
        raise ValueError(f"Invalid time string: {time_str}.")

    def energy(self, freq: str = "1d") -> pl.DataFrame:
        """Calculate the AC energy output of the PV plant.

        We assume that within the interval, the power output is constant. Therefore we will not use numerical
        integration to calculate the energy, but simply multiply the power output with the interval length
        (and sum it up if freq > 1H)

        :param freq: The frequency of the energy output. See polars docs for valid options.
        :return: A pl.Series with the energy output of the PV plant.
        """
        if self.ac_power is None:
            raise ValueError(
                "AC power output is not available, cannot calculate energy. Run simulation first."
            )
        if "".join(filter(str.isalpha, freq)) not in VALID_DOWN_SAMPLE_FREQ:
            raise ValueError(
                f"Invalid frequency suffix. Must be one of {VALID_DOWN_SAMPLE_FREQ}."
            )

        # check data frequency
        if self.frequency > SECONDS_PER_HOUR:
            raise ValueError(
                f"Cannot calculate energy for data with frequency {self.frequency}s. Must be <= 1H."
            )

        # compute the conversion factor from power to energy
        conversion_factor = self.frequency / SECONDS_PER_HOUR
        ac_energy: pl.DataFrame = self.ac_power.select(
            pl.col("datetime"), pl.col("ac_power") * conversion_factor
        )

        # compute the energy output per period
        ac_energy = (
            ac_energy.sort(by="datetime")
            .group_by_dynamic("datetime", every=freq)
            .agg(pl.col("ac_power").sum().alias("ac_energy").cast(pl.Int64))
        )
        return ac_energy


@dataclass
class PowerEstimate(ABC):
    """Abstract base class to do PV power estimation."""

    location: Location = field(repr=False)
    pv_plant: PVPlantModel = field(repr=False)
    type: ForecastType = field(default=ForecastType.LIVE)
    _result: ForecastResult | None = field(repr=False, default=None)

    def run(self, weather_df: pl.DataFrame | None = None) -> ForecastResult:
        """Run power estimate and store results in self._result.

        :param weather_df: The weather data or datetimes to forecast for.
        :return: A ForecastResult object containing the results of the power estimate.
        """
        # prepare weather data / datetimes
        weather_df = self._prepare_weather(weather_df)

        # run the forecast for each model chain
        result_df = pl.DataFrame(weather_df["datetime"])
        for model_chain in self.pv_plant.models:
            # set the model chain attributes
            for attr, val in self.model_chain_attrs.items():
                setattr(model_chain, attr, val)
            model_chain.run_model(weather_df.to_pandas().set_index("datetime"))

            # add the results to the results DataFrame
            ac: pl.Series = pl.from_pandas(model_chain.results.ac, include_index=False)
            result_df = result_df.with_columns(ac.alias(model_chain.name))

        # sum the results of all model chains horizontally and return the ForecastResult
        results = result_df.select("datetime").with_columns(
            result_df.select(pl.exclude("datetime"))
            .sum_horizontal()
            .alias("ac_power")
            .cast(pl.Int64)
        )
        return ForecastResult(name=self.pv_plant.name, type=self.type, ac_power=results)

    @abstractmethod
    def _prepare_weather(self, weather_df: pl.DataFrame | None = None) -> pl.DataFrame:
        """
        Prepare weather data for the forecast. This method should be implemented by subclasses.

        When calling this function it may be optional or mandatory to provide weather
        data or datetimes to forecast for. Datetimes must always be ordered and provided
        in a column named 'datetime'. Weather data must be provided in a DataFrame with
        the following columns: [datetime, cloud_cover, wind_speed, temperature, humidity,
        dni, dhi, ghi]. Other columns are ignored.
        """

    @staticmethod
    def _add_percepitable_water(
        weather_df: pl.DataFrame,
        temp_col: str = "temperature",
        rh_col: str = "humidity",
    ) -> pl.DataFrame:
        """
        Add the precipitable water column to the weather data.

        Gueymard94_pw alculates precipitable water (cm) from ambient air temperature (C) and
        relatively humidity (%) using an empirical model. The accuracy of this method is
        approximately 20% for moderate PW (1-3 cm) and less accurate otherwise.

        Precipitable water is the depth of water in a column of the atmosphere, if all
        the water in that column were precipitated as rain.

        See: https://pvlib-python.readthedocs.io/en/stable/_modules/pvlib/atmosphere.html#gueymard94_pw

        :param weather_df: The weather data to use for the simulation.
        :param temp_col: The name of the column in weather_df that contains the temperature data.
        :param rh_col: The name of the column in weather_df that contains the relative humidity data.
        :return: The weather data with the preciptable_water column added.
        """
        if not {"temperature", "humidity"}.issubset(weather_df.columns):
            raise ValueError("Weather data must contain 'temperature' and 'humidity'.")
        temperature = weather_df[temp_col].to_numpy()
        humidity = weather_df[rh_col].to_numpy()
        precipitable_water = gueymard94_pw(temperature, humidity)
        return weather_df.with_columns(
            pl.Series("precipitable_water", precipitable_water)
        )

    @property
    @abstractmethod
    def model_chain_attrs(self) -> dict[str, str]:
        """Return the attributes to set on the model chain."""

    @property
    def result(self) -> ForecastResult:
        """Return the result of the power estimate."""
        if self._result is None:
            raise ValueError("Power estimate has not been run yet. Run .run() first.")
        return self._result


@dataclass
class Live(PowerEstimate):
    """Class for PV power forecasts based on live weather data."""

    type: ForecastType = field(default=ForecastType.LIVE)

    @property
    def model_chain_attrs(self) -> dict[str, str]:
        return {}

    def _prepare_weather(self, weather_df: pl.DataFrame | None = None) -> pl.DataFrame:
        if weather_df is None:
            raise ValueError("Must provide weather data.")
        return self._add_percepitable_water(weather_df)


@dataclass
class Clearsky(PowerEstimate):
    """Class for PV power forecasts based on weather data."""

    type: ForecastType = field(default=ForecastType.CLEARSKY)

    def _prepare_weather(self, weather_df: pl.DataFrame | None = None) -> pl.DataFrame:
        if weather_df is None:
            raise ValueError("Must provide weather data.")

        # convert datetimes to strings
        dt_strings = pd.DatetimeIndex(
            weather_df["datetime"].dt.strftime("%Y-%m-%dT%H:%M:%S%z")
        )
        cs = self.location.get_clearsky(dt_strings)
        return weather_df.with_columns(
            pl.Series("ghi", cs["ghi"]),
            pl.Series("dni", cs["dni"]),
            pl.Series("dhi", cs["dhi"]),
        )

    @property
    def model_chain_attrs(self) -> dict[str, str]:
        return {"aoi_model": "physical", "spectral_model": "no_loss"}


@dataclass
class Historical(PowerEstimate):
    """Class for PV power forecasts based on weather data."""

    type: ForecastType = field(default=ForecastType.HISTORICAL)
    _pvgis_data_path: Path = field(init=False, repr=False, default=Path())

    def __post_init__(self) -> None:
        lat = str(round(self.location.latitude, 4)).replace(".", "_")
        lon = str(round(self.location.longitude, 4)).replace(".", "_")
        self._pvgis_data_path = Path(f"pvcast/data/pvgis/pvgis_tmy_{lat}_{lon}.csv")

    def _prepare_weather(self, weather_df: pl.DataFrame = None) -> pl.DataFrame:
        tmy_data = self.get_pvgis_data()
        tmy_data.index = pl.date_range(
            start=f"{HISTORICAL_YEAR_MAPPING}-01-01 00:00",
            end=f"{HISTORICAL_YEAR_MAPPING}-12-31 23:00",
            freq="1H",
            tz="UTC",
        )

        # if there are no specifically requested dates, return the entire TMY dataset
        if weather_df is None:
            return tmy_data

        # get start and end dates we want to obtain TMY data for
        start_date = weather_df.index[0].replace(year=HISTORICAL_YEAR_MAPPING)
        end_date = weather_df.index[-1].replace(year=HISTORICAL_YEAR_MAPPING)

        # get the corresponding TMY data
        return tmy_data.loc[start_date:end_date]

    @property
    def model_chain_attrs(self) -> dict[str, str]:
        return {}

    def get_pvgis_data(
        self, save_data: bool = True, force_api: bool = False
    ) -> pl.DataFrame:
        """
        Retrieve the PVGIS data using the PVGIS API. Returned data should include the following columns:
        [temp_air, relative_humidity, ghi, dni, dhi, wind_speed]. Other columns are ignored.

        If the path is provided, columnnames of the supplied CSV file must follow the same naming convention.

        :param path: The path to the PVGIS data file in CSV format. If None, the data is retrieved using the PVGIS API.
        :param save_data: If True, data retrieved from the API is saved to the path so it can be reused later.
        :return: PVGIS pl.DataFrame.
        """
        from_file = self._pvgis_data_path.exists() and not force_api
        if from_file:
            # read data from CSV file
            _LOGGER.debug("Reading PVGIS data from file at: %s.", self._pvgis_data_path)
            tmy_data = pl.read_csv(
                self._pvgis_data_path, index_col=0, parse_dates=True, header=0
            )
        else:
            _LOGGER.debug("Retrieving PVGIS data from API.")
            # create parent directory
            self._pvgis_data_path.parent.mkdir(parents=True, exist_ok=True)

            # 4th decimal is accurate to 11.1m
            lat = round(self.location.latitude, 4)
            lon = round(self.location.longitude, 4)
            tmy_data, __, __, __ = get_pvgis_tmy(
                latitude=lat,
                longitude=lon,
                outputformat="json",
                startyear=2005,
                endyear=2016,
                map_variables=True,
            )

        # change column names to match the model chain
        tmy_data.index.name = "datetime"
        tmy_data = tmy_data.tz_convert("UTC")

        # check if data is complete
        if tmy_data.isnull().values.any():
            raise ValueError("PVGIS data contains NaN values.")

        # add preciptable_water to weather_df if it is not in the weather data already
        tmy_data = self._add_percepitable_water(tmy_data)

        # save data to CSV file if it was retrieved from the API
        if not from_file and save_data:
            tmy_data.to_csv(self._pvgis_data_path)
        return tmy_data
