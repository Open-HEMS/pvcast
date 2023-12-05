"""Model based PV power forecasting."""

from __future__ import annotations

import copy
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl
from pvlib.atmosphere import gueymard94_pw
from pvlib.iotools import get_pvgis_tmy
from pvlib.location import Location

from .const import (
    HISTORICAL_YEAR_MAPPING,
    SECONDS_PER_DAY,
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
        if "time" not in self.ac_power.columns:
            raise ValueError("AC power data must have a 'time' column.")
        if self.ac_power["time"].dtype != pl.Datetime:
            raise ValueError(
                f"Time column must have dtype datetime.datetime. Got {self.ac_power['time'].dtype}."
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
            fc_result_cpy.ac_power.sort(by="time")
            .upsample(time_column="time", every=freq, maintain_order=True)
            .select(pl.all().forward_fill())
        )
        return fc_result_cpy

    @property
    def frequency(self) -> int:
        """Return the frequency of the data in seconds.
        NB: This is actually the data interval, not the frequency.
        NB: We assume that the interval is constant throughout the data.
        """
        t0 = self.ac_power.select(pl.col("time"))[0].item()
        t1 = self.ac_power.select(pl.col("time"))[1].item()
        return int(self._timedelta_to_pl_duration(t1 - t0)[:-1])

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

    def _timedelta_to_pl_duration(self, td: timedelta | str | None) -> str | None:
        """Convert python timedelta to a polars duration string.
        This function is copied from polars' utils.py.
        """
        if td is None or isinstance(td, str):
            return td

        if td.days >= 0:
            d = td.days and f"{td.days}d" or ""
            s = td.seconds and f"{td.seconds}s" or ""
            us = td.microseconds and f"{td.microseconds}us" or ""
        else:
            if not td.seconds and not td.microseconds:
                d = td.days and f"{td.days}d" or ""
                s = ""
                us = ""
            else:
                corrected_d = td.days + 1
                d = corrected_d and f"{corrected_d}d" or "-"
                corrected_seconds = SECONDS_PER_DAY - (
                    td.seconds + (td.microseconds > 0)
                )
                s = corrected_seconds and f"{corrected_seconds}s" or ""
                us = td.microseconds and f"{10**6 - td.microseconds}us" or ""

        return f"{d}{s}{us}"

    def energy(self, freq: str = "1d") -> pl.DataFrame:
        """Calculate the AC energy output of the PV plant.

        We assume that within the interval, the power output is constant. Therefore we will not use numerical
        integration to calculate the energy, but simply multiply the power output with the interval length
        (and sum it up if freq > 1H)

        :param freq: The frequency of the energy output. See pandas.resample() for valid options.
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

        # compute the conversion factor != 1 if frequency < 1H
        conversion_factor = self.frequency / SECONDS_PER_HOUR
        ac_energy: pl.DataFrame = self.ac_power.select(
            pl.col("time"), pl.col("ac_power") * conversion_factor
        )

        # compute the energy output per period
        ac_energy = (
            ac_energy.sort(by="time")
            .group_by_dynamic("time", every=freq)
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
        results = pl.DataFrame()
        for idx, model_chain in enumerate(self.pv_plant.models):
            # set the model chain attributes
            for attr, val in self.model_chain_attrs.items():
                setattr(model_chain, attr, val)
            model_chain.run_model(weather_df)

            # add the results to the results DataFrame
            res = model_chain.results.ac
            _LOGGER.debug("res type: %s", type(res))
            # convert to polars df
            res = pl.from_pandas(res)
            _LOGGER.debug("res : %s", res)

        # create a ForecastResult object
        result = ForecastResult(
            name=self.pv_plant.name, type=self.type, ac_power=results
        )
        self._result = result
        return result

    @abstractmethod
    def _prepare_weather(self, weather_df: pl.DataFrame = None) -> pl.DataFrame:
        """Prepare weather data for the forecast."""
        raise NotImplementedError

    def _add_percepitable_water(
        self,
        weather_df: pl.DataFrame,
        temp_col: str = "temp_air",
        rh_col: str = "relative_humidity",
    ) -> pl.DataFrame:
        """Add preciptable_water to weather_df if it is not in the weather data already.

        :param weather_df: The weather data to use for the simulation.
        :param temp_col: The name of the column in weather_df that contains the temperature data.
        :param rh_col: The name of the column in weather_df that contains the relative humidity data.
        :return: The weather data with the preciptable_water column added.
        """
        if "precipitable_water" not in weather_df.columns:
            weather_df["precipitable_water"] = gueymard94_pw(
                weather_df[temp_col], weather_df[rh_col]
            )
        return weather_df

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

    def _prepare_weather(self, weather_df: pl.DataFrame = None) -> pl.DataFrame:
        # add preciptable_water to weather_df if it is not in the weather data already
        weather_df.rename(
            columns={"temperature": "temp_air", "humidity": "relative_humidity"},
            inplace=True,
        )
        weather_df = self._add_percepitable_water(weather_df)
        return weather_df


@dataclass
class Clearsky(PowerEstimate):
    """Class for PV power forecasts based on weather data."""

    type: ForecastType = field(default=ForecastType.CLEARSKY)

    def _prepare_weather(self, weather_df: pl.DataFrame = None) -> pl.DataFrame:
        return self.location.get_clearsky(weather_df.index)

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
        tmy_data.index.name = "time"
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
