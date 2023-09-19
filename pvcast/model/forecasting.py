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
from pvlib.modelchain import ModelChainResult

from .const import VALID_FREQS

if TYPE_CHECKING:
    from .model import PVPlantModel


_LOGGER = logging.getLogger(__name__)


class ForecastType(str, Enum):
    """Enum for the type of PVPlantResults."""

    FORECAST = "forecast"
    CLEARSKY = "clearsky"
    HISTORICAL = "historic"


@dataclass
class ForecastResult:
    """Object to store the aggregated results of the PVPlantModel simulation.

    :param name: The name of the PV plant.
    :param type: The type of the result: forecast based on weather data, clearsky, or historic based on PVGIS.
    :param ac_power: The sum of AC power outputs of all ModelChain objects in the PV plant.
    :param dc_power: If available, DC power broken down into individual arrays. Each array is a column in the DataFrame.
    :param freq: Frequency of original data. Can be "1H" for hourly, "1D" for daily, "M" for monthly, "A" for yearly.
    :param weather: The input weather data used for the simulation. For debugging purposes only.
    :param modelresults: The input raw data, list of pvlib ModelChainResult objects. For debugging purposes only.
    """

    name: str
    type: ForecastType
    ac_power: pd.Series = field(repr=False, default=None)
    dc_power: tuple[pd.Series] = field(repr=False, default=None)
    freq: str = field(repr=False, default="1H")
    weather: pd.DataFrame = field(repr=False, default=None)
    modelresults: list[ModelChainResult] = field(repr=False, default=None)

    def __post_init__(self):
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
            raise ValueError(f"Frequency {freq} not supported. Must be one of {VALID_FREQS}.")
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
        plant_cpy.ac_power = res_f(plant_cpy.ac_power)
        return plant_cpy

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
            raise AttributeError("no discernible frequency found to `idx`.  Specify a frequency string with `freq`.")
        return idx

    def energy(self, freq: str = "1D") -> pd.Series:
        """Calculate the AC energy output of the PV plant.

        :param freq: The frequency of the energy output. See pandas.resample() for valid options.
        :return: A pd.Series with the energy output of the PV plant.
        """
        if self.ac_power is None:
            raise ValueError("AC power output is not available, cannot calculate energy. Run simulation first.")
        if VALID_FREQS.index(freq) > VALID_FREQS.index("1H"):
            raise ValueError(
                "For forecast with future weather data energy can only be calculated up to hourly interval."
            )
        if VALID_FREQS.index(freq) > VALID_FREQS.index(self.freq):
            raise ValueError(
                f"Cannot calculate energy for a frequency higher than the fundamental data frequency ({self.freq})."
            )

        # resample to hourly frequency and then sum to get Wh
        plant_cpy = self.resample("1H")
        ac_energy = plant_cpy.ac_power.resample(freq).sum()
        return ac_energy


@dataclass
class PowerEstimate(ABC):
    """Abstract base class to do PV power estimation."""

    type: ForecastType = field(default=ForecastType.FORECAST)
    location: Location = field(repr=False, default=None)
    pv_plant: PVPlantModel = field(repr=False, default=None)
    _result: ForecastResult = field(repr=False, default=None)

    def run(self, weather_df: pd.DataFrame = None) -> ForecastResult:
        """Run power estimate and store results in self._result.

        :param weather_df: The weather data to use for the simulation. Not required if type is ForecastType.HISTORICAL.
                    If type is ForecastType.CLEARSKY, weather_df requires only pd.Timestamps to forecast. Actual
                    weather data can be provided, but will be ignored.
        """
        # if isinstance(weather_df, pd.DatetimeIndex), convert to pd.DataFrame with index = weather_df
        if isinstance(weather_df, pd.DatetimeIndex):
            weather_df = pd.DataFrame(index=weather_df)

        # prepare weather data / datetimes
        weather_df: pd.DataFrame = self._prepare_weather(weather_df)

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
            modelresults=results,
            weather=weather_df,
        )
        self._result = result
        return result

    @abstractmethod
    def _prepare_weather(self, weather_df: pd.DataFrame = None) -> pd.DataFrame:
        """Prepare weather data for the forecast. The default implementation simply returns the input weather_df.

        :param weather_df: The weather data to use for the simulation. Not required if type is ForecastType.HISTORICAL.
                    If type is ForecastType.CLEARSKY, weather_df requires only pd.Timestamps to forecast. Actual
                    weather data can be provided, but will be ignored.
        :return: The prepared weather data.
        """
        return weather_df

    def _add_percepitable_water(
        self, weather_df: pd.DataFrame, temp_col: str = "temp_air", rh_col: str = "relative_humidity"
    ) -> pd.DataFrame:
        """Add preciptable_water to weather_df if it is not in the weather data already.

        :param weather_df: The weather data to use for the simulation.
        :param temp_col: The name of the column in weather_df that contains the temperature data.
        :param rh_col: The name of the column in weather_df that contains the relative humidity data.
        :return: The weather data with the preciptable_water column added.
        """
        if "precipitable_water" not in weather_df.columns:
            weather_df["precipitable_water"] = gueymard94_pw(weather_df[temp_col], weather_df[rh_col])
        return weather_df

    @property
    @abstractmethod
    def model_chain_attrs(self) -> dict:
        """Return the attributes to set on the model chain."""

    @property
    def result(self) -> ForecastResult:
        """Return the result of the power estimate."""
        if self._result is None:
            raise ValueError("Power estimate has not been run yet. Run .run() first.")
        return self._result


@dataclass
class Forecast(PowerEstimate):
    """Class for PV power forecasts based on weather data."""

    type: ForecastType = field(default=ForecastType.FORECAST)

    @property
    def model_chain_attrs(self) -> dict:
        return {}

    def _prepare_weather(self, weather_df: pd.DataFrame = None) -> pd.DataFrame:
        # add preciptable_water to weather_df if it is not in the weather data already
        weather_df.rename(columns={"temperature": "temp_air", "humidity": "relative_humidity"}, inplace=True)
        weather_df = self._add_percepitable_water(weather_df)
        return weather_df


@dataclass
class Clearsky(PowerEstimate):
    """Class for PV power forecasts based on weather data."""

    type: ForecastType = field(default=ForecastType.CLEARSKY)

    def _prepare_weather(self, weather_df: pd.DataFrame = None) -> pd.DataFrame:
        return self.location.get_clearsky(weather_df.index)

    @property
    def model_chain_attrs(self) -> dict:
        return {"aoi_model": "physical", "spectral_model": "no_loss"}


@dataclass
class Historical(PowerEstimate):
    """Class for PV power forecasts based on weather data."""

    type: ForecastType = field(default=ForecastType.HISTORICAL)
    _pvgis_data_path: Path = field(init=False, repr=False, default=None)

    def __post_init__(self):
        lat = str(round(self.location.latitude, 4)).replace(".", "_")
        lon = str(round(self.location.longitude, 4)).replace(".", "_")
        self._pvgis_data_path = Path(f"pvcast/data/pvgis/pvgis_tmy_{lat}_{lon}.csv")

    def _prepare_weather(self, weather_df: pd.DataFrame = None) -> pd.DataFrame:
        tmy_data = self.get_pvgis_data()
        tmy_data.index = pd.date_range(start="2021-01-01 00:00", end="2021-12-31 23:00", freq="1H")
        return tmy_data

    @property
    def model_chain_attrs(self) -> dict:
        return {}

    def get_pvgis_data(self, save_data: bool = True, force_api: bool = False) -> pd.DataFrame:
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
            tmy_data = pd.read_csv(self._pvgis_data_path, index_col=0, parse_dates=True, header=0)
        else:
            _LOGGER.debug("Retrieving PVGIS data from API.")
            # create parent directory
            self._pvgis_data_path.parent.mkdir(parents=True, exist_ok=True)

            # 4th decimal is accurate to 11.1m
            lat = round(self.location.latitude, 4)
            lon = round(self.location.longitude, 4)
            tmy_data, __, __, __ = get_pvgis_tmy(
                latitude=lat, longitude=lon, outputformat="json", startyear=2005, endyear=2016, map_variables=True
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
