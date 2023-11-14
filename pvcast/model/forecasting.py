"""Model based PV power forecasting."""

from __future__ import annotations

import copy
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from pvlib.atmosphere import gueymard94_pw
from pvlib.iotools import get_pvgis_tmy
from pvlib.location import Location

from .const import HISTORICAL_YEAR_MAPPING, VALID_FREQS

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
    :param dc_power: If available, DC power broken down into individual arrays. Each array is a column in the DataFrame.
    :param freq: Frequency of original data. Can be "1H" for hourly, "1D" for daily, "M" for monthly, "A" for yearly.
    """

    name: str
    type: ForecastType
    ac_power: pd.Series | None = field(repr=False, default=None)
    dc_power: tuple[pd.Series] | None = field(repr=False, default=None)
    freq: str = field(repr=False, default="1H")

    def __post_init__(self) -> None:
        """Post-initialization function."""
        if self.ac_power is not None and self.ac_power.index.freq is None:
            self.ac_power.index = self._add_freq(self.ac_power.index)

    def resample(self, freq: str, interp_method: str = "linear") -> ForecastResult:
        """Resample the entire ForecastResult to a new interval.

        :param freq: The frequency of the energy output. See pandas.resample() for valid options.
        :param interp_method: The interpolation method to use. Any option of pd.interpolate() is valid.
        :return: A new ForecastResult object with the resampled data.
        """
        if freq not in VALID_FREQS:
            raise ValueError(
                f"Frequency {freq} not supported. Must be one of {VALID_FREQS}."
            )
        if freq == self.freq:
            return self

        # define resample function
        def res_f(vals: pd.DataFrame) -> pd.DataFrame:
            res = vals.resample(freq).mean().interpolate(interp_method)
            res.index = self._add_freq(res.index, freq)
            return res

        plant_cpy = copy.deepcopy(self)
        plant_cpy.freq = freq

        # resample all pd.Series attributes
        plant_cpy.ac_power = res_f(plant_cpy.ac_power).astype("int64")
        return plant_cpy

    def _add_freq(
        self, idx: pd.DatetimeIndex, freq: str | None = None
    ) -> pd.DatetimeIndex:
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
                "No discernible frequency found to `idx`. Specify a frequency string with `freq`."
            )
        return idx

    def energy(self, freq: str = "1D") -> pd.Series:
        """Calculate the AC energy output of the PV plant.

        We assume that within the interval, the power output is constant. Therefore we will not use numerical
        integration to calculate the energy, but simply multiply the power output with the interval length
        (and sum it up if freq > 1H)

        :param freq: The frequency of the energy output. See pandas.resample() for valid options.
        :return: A pd.Series with the energy output of the PV plant.
        """
        if self.ac_power is None:
            raise ValueError(
                "AC power output is not available, cannot calculate energy. Run simulation first."
            )

        # check if freq is ambiguous (monthly, yearly)
        ambiguous = freq in ("M", "A")

        if not ambiguous and pd.Timedelta(freq) < pd.Timedelta(
            self.ac_power.index.freq
        ):
            raise ValueError(
                f"Cannot calculate energy for a frequency higher than the fundamental data frequency \
                ({self.ac_power.index.freq})."
            )

        # if freq > 1H, we calculate the energy for each hour and sum it up
        # we must verify that: freq(ac_power) <= 1H
        if pd.Timedelta(self.ac_power.index.freq) > pd.Timedelta("1H"):
            raise ValueError(
                f"AC power interval ({self.ac_power.index.freq}) must be <= 1H in order to calculate valid energy data."
            )

        # ac_power [W, freq] -> ac_energy [Wh] conversion factor
        conv_factor = 1
        if not ambiguous and pd.Timedelta(freq) < pd.Timedelta("1H"):
            conv_factor = pd.Timedelta(freq).total_seconds() / 3600

        ac_energy = self.ac_power * conv_factor

        # now that AC energy has unit Wh, we can resample to the desired frequency and sum
        return ac_energy.resample(freq).sum().round(0).astype("int64")

    @property
    def ac_energy(self) -> pd.Series:
        """Calculate the AC energy output of the PV plant.

        :return: A pd.Series with the energy output of the PV plant.
        """
        if self.ac_power is None:
            raise ValueError(
                "AC power output is not available, cannot calculate energy. Run simulation first."
            )
        return self.energy(freq=self.ac_power.index.freq)


@dataclass
class PowerEstimate(ABC):
    """Abstract base class to do PV power estimation."""

    location: Location = field(repr=False)
    pv_plant: PVPlantModel = field(repr=False)
    type: ForecastType = field(default=ForecastType.LIVE)
    _result: ForecastResult | None = field(repr=False, default=None)

    def run(self, weather_df: pd.DataFrame | None = None) -> ForecastResult:
        """Run power estimate and store results in self._result.

        :param weather_df: The weather data or datetimes to forecast for.
        :return: A ForecastResult object containing the results of the power estimate.
        """
        # if isinstance(weather_df, pd.DatetimeIndex), convert to pd.DataFrame with index = weather_df
        if isinstance(weather_df, pd.DatetimeIndex):
            weather_df = pd.DataFrame(index=weather_df)

        # prepare weather data / datetimes
        weather_df = self._prepare_weather(weather_df)

        # run the forecast for each model chain
        results = []
        for model_chain in copy.deepcopy(self.pv_plant.models):
            # set the model chain attributes
            for attr, val in self.model_chain_attrs.items():
                setattr(model_chain, attr, val)
            model_chain.run_model(weather_df)
            results.append(model_chain.results)

        # aggregate the results
        ac_power = self.pv_plant.aggregate(results, "ac")
        result = ForecastResult(
            name=self.pv_plant.name,
            type=self.type,
            ac_power=ac_power,
            dc_power=None,
            freq=ac_power.index.freq,
        )
        self._result = result
        return result

    @abstractmethod
    def _prepare_weather(self, weather_df: pd.DataFrame = None) -> pd.DataFrame:
        """Prepare weather data for the forecast."""
        raise NotImplementedError

    def _add_percepitable_water(
        self,
        weather_df: pd.DataFrame,
        temp_col: str = "temp_air",
        rh_col: str = "relative_humidity",
    ) -> pd.DataFrame:
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

    def _prepare_weather(self, weather_df: pd.DataFrame = None) -> pd.DataFrame:
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

    def _prepare_weather(self, weather_df: pd.DataFrame = None) -> pd.DataFrame:
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

    def _prepare_weather(self, weather_df: pd.DataFrame = None) -> pd.DataFrame:
        tmy_data = self.get_pvgis_data()
        tmy_data.index = pd.date_range(
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
    ) -> pd.DataFrame:
        """
        Retrieve the PVGIS data using the PVGIS API. Returned data should include the following columns:
        [temp_air, relative_humidity, ghi, dni, dhi, wind_speed]. Other columns are ignored.

        If the path is provided, columnnames of the supplied CSV file must follow the same naming convention.

        :param path: The path to the PVGIS data file in CSV format. If None, the data is retrieved using the PVGIS API.
        :param save_data: If True, data retrieved from the API is saved to the path so it can be reused later.
        :return: PVGIS pd.DataFrame.
        """
        from_file = self._pvgis_data_path.exists() and not force_api
        if from_file:
            # read data from CSV file
            _LOGGER.debug("Reading PVGIS data from file at: %s.", self._pvgis_data_path)
            tmy_data = pd.read_csv(
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
