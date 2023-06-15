"""Implements a PV system model."""

from __future__ import annotations

import copy
import logging
from dataclasses import InitVar, dataclass, field
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import List, Optional, Tuple

import pandas as pd
import pvlib
import pytz
from pandas import DataFrame, DatetimeIndex, Series
from pvlib.location import Location
from pvlib.modelchain import ModelChain, ModelChainResult
from pvlib.pvsystem import Array, FixedMount, PVSystem
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS
from pytz import BaseTzInfo, timezone

from .const import BASE_CEC_DATA_PATH

_LOGGER = logging.getLogger(__name__)


class ForecastType(str, Enum):
    """Enum for the type of PVPlantResults."""

    FORECAST = "forecast"
    CLEARSKY = "clearsky"
    HISTORICAL = "historic"


@dataclass
class PVPlantResult:
    """Object to store the aggregated results of the PVPlantModel simulation.

    :param name: The name of the PV plant.
    :param type: The type of the result: forecast based on weather data, clearsky, or historic based on PVGIS.
    :param ac: The AC power output of the aggregated ModelChains in PV plant.
    :param weather: The weather data used for the simulation.
    :param pvlibresults: Raw data, list of pvlib ModelChainResult objects.
    """

    name: str
    type: ForecastType
    ac: Series = field(repr=False)
    weather: DataFrame = field(repr=False)
    pvlibresults: list[ModelChainResult] = field(repr=False)


@dataclass
class PVPlantModel:
    """
    Implements the entire PV model chain based on the parameters set in config.yaml. This class is basically a wrapper
    around pvlib. Each entry in the plant list in config.yaml file should be instantiated as a PVModelChain object.
    In case of a PV system with microinverters, each microinverter is represented by one PVModelChain object.

    For example, if the plant entry in config.yaml is:

    plant:
        # PVModelChain object 1
        - name: EastWest
        ...
        # PVModelChain object 2
        - name: NorthSouth
        ...

    Then we should have two PVPlantModel objects, one for each entry in the list under `plant:` in config.yaml.

    :param config: The PV plant configuration dictionary. TODO: add validation via voluptuous.
    :param loc: The location of the PV plant.
    """

    config: InitVar[dict]
    location: Location = field(repr=False)
    inv_param: DataFrame = field(repr=False)
    mod_param: DataFrame = field(repr=False)
    temp_param: dict = field(default_factory=lambda: TEMPERATURE_MODEL_PARAMETERS["pvsyst"]["freestanding"], repr=False)
    _pv_plant: list[ModelChain] = field(init=False, repr=False)
    name: str = field(init=False)
    _forecast: PVPlantResult | None = field(init=False, repr=False)
    _clearsky: PVPlantResult | None = field(init=False, repr=False)
    _historic: PVPlantResult | None = field(init=False, repr=False)

    def __post_init__(self, config: dict):
        pv_systems = self._create_pv_systems(config)
        self._pv_plant = self._build_model_chain(pv_systems, self.location, config["name"])
        self.name = config["name"]

    @property
    def forecast(self) -> PVPlantResult | None:
        """Return the forecast results of the PV plant."""
        return self._forecast

    @property
    def clearsky(self) -> PVPlantResult | None:
        """Return the clearsky results of the PV plant."""
        return self._clearsky

    @property
    def historic(self) -> PVPlantResult | None:
        """Return the historic results of the PV plant."""
        return self._historic

    def _create_pv_systems(self, config: dict) -> list[PVSystem]:
        """
        Create the PV system. This method is called by __post_init__.

        In case of a PV system with microinverters, each microinverter is represented by one PVSystem object.
        """
        # _LOGGER.debug("Creating PV system model for system %s", config["name"])
        print(f"Creating PV system model for system {config['name']}")
        micro: bool = config["microinverter"]
        inverter: str = config["inverter"]
        arrays: list = config["arrays"]
        name: str = config["name"]

        # system uses microinverters, create one model chain for each PV module
        if micro:
            pv_systems = self._build_system_micro(arrays, inverter, name)
        # system uses a single inverter, create one model chain for the whole system
        else:
            pv_systems = self._build_system_string(arrays, inverter, name)
        return pv_systems

    def _build_system_micro(self, arrays: list[dict], inverter: str, name: str | None = None) -> list[PVSystem]:
        """Build a PV system model for a system with microinverters.

        :param arrays: List of PV arrays.
        :param inverter: The inverter model.
        :param name: The name of the PV system.
        :return: List of PV system model chains.
        """
        pv_systems = []

        # create a PVSystem for each microinverter
        for _, array in enumerate(arrays):
            n_modules = array["strings"] * array["modules_per_string"]
            mount = FixedMount(surface_tilt=array["tilt"], surface_azimuth=array["azimuth"])
            module_param = self._retrieve_parameters(array["module"], inverter=False)
            inv_param = self._retrieve_parameters(inverter, inverter=True)

            # each module has it's own inverter therefore must have its own PVSystem
            for module_id in range(n_modules):
                module_name = f"{array['name']}_array_{module_id}"

                # define PV array
                arr = Array(
                    mount=mount,
                    module_parameters=module_param,
                    temperature_model_parameters=self.temp_param,
                    strings=1,
                    modules_per_string=1,
                    name=module_name,
                )

                # define PVSystem
                pv_system = PVSystem(
                    arrays=[arr],
                    inverter_parameters=inv_param,
                    inverter=inverter,
                    name=name,
                )
                pv_systems.append(pv_system)

        return pv_systems

    def _build_system_string(self, arrays: list[dict], inverter: str, name: str | None = None) -> list[PVSystem]:
        """Build a PV system model for a system with a regular string inverter.

        :param arrays: List of PV arrays.
        :param inverter: The inverter model.
        :param name: The name of the PV system.
        :return: List of PV system model chains.
        """
        pv_arrays = []

        # a string system uses one inverter so we aggregate all arrays into one PVSystem
        for array_id, array in enumerate(arrays):
            mount = FixedMount(surface_tilt=array["tilt"], surface_azimuth=array["azimuth"])
            module_param = self._retrieve_parameters(array["module"], inverter=False)

            # define PV array
            arr = Array(
                mount=mount,
                module_parameters=module_param,
                temperature_model_parameters=self.temp_param,
                strings=array["strings"],
                modules_per_string=array["modules_per_string"],
                name=f"{array['name']}_array_{array_id}",
            )
            pv_arrays.append(arr)

        # create the PV system
        inv_param = self._retrieve_parameters(inverter, inverter=True)
        pv_system = PVSystem(
            arrays=pv_arrays,
            inverter_parameters=inv_param,
            inverter=inverter,
            name=name,
        )

        return [pv_system]

    def _retrieve_parameters(self, device: str, inverter: bool) -> dict:
        """Retrieve module or inverter parameters from the pvlib/SAM databases.

        :param device: The name of the module or inverter.
        :param inverter: True if the device is an inverter, False if it is a PV module.
        :return: The parameters of the device.
        """
        # retrieve parameter database
        candidates = self.inv_param if inverter else self.mod_param

        # check if there are duplicates
        duplicates = candidates[candidates.index.duplicated(keep=False)]
        if not duplicates.empty:
            _LOGGER.debug("Dropping %s duplicate entries.", len(duplicates))
            candidates = candidates.drop_duplicates(keep="first")

        # check if device is in the database
        try:
            params = candidates.loc[candidates.index == device].to_dict("records")[0]
            _LOGGER.debug("Found device %s in the database.", device)
        except KeyError as exc:
            raise KeyError(f"Device {device} not found in the database.") from exc

        return params

    def _build_model_chain(self, pv_systems: list[PVSystem], location: Location, name: str) -> list[ModelChain]:
        """Build the model chains for the list of PV systems.

        :param pv_systems: List of PVSystem objects.
        :param name: The name of the PV plant.
        :param location: The location of the PV plant.
        :return: List of model chains.
        """
        return [ModelChain(system, location, name=name, aoi_model="physical") for system in pv_systems]

    def run_forecast(self, weather_df: pd.DataFrame) -> None:
        """Run the forecast for the PV system based on short term weather data.

        :param weather_df: The weather forecast DataFrame.
        """
        # run the forecast for each model chain
        results = []
        for model_chain in self._pv_plant:
            model_chain.run_model(weather_df)
            results.append(model_chain.results)

        # combine the results
        self._forecast = self._aggregate(results, "ac")

    def run_clearsky(self, datetimes: pd.DatetimeIndex) -> None:
        """Run the forecast for the PV system based on clear sky weather data obtained from the location object."""
        # get clear sky weather data
        weather_df = self.location.get_clearsky(datetimes)

        # run the forecast for each model chain
        plant_copy = copy.deepcopy(self._pv_plant)

        results = []
        for model_chain in plant_copy:
            # set aoi_model to "physical" and spectral_model to "no_loss" to use the clear sky data
            model_chain.aoi_model = "physical"
            model_chain.spectral_model = "no_loss"
            model_chain.run_model(weather_df)
            results.append(model_chain.results)

        # combine the results
        self._clearsky = self._aggregate(results, "ac")

    def run_historic(self, freq: str = "M") -> None:
        """Run simulation for the PV system based on TMY historic weather data obtained from PVGIS.

        :param freq: Freq of returned results. Can be "H" for hourly, "D" for daily, "M" for monthly, "A" for annual.
        """
        raise NotImplementedError

    def _aggregate(self, results: list[ModelChainResult], key: str) -> Series:
        """Aggregate the results of the model chains into a single dataframe.

        :param results: List of model chain result objects.
        :param key: The key to aggregate on. Can be "ac", "dc", ..., but currently only "ac" is supported.
        :return: The aggregated results.
        """
        # check if key is valid
        if key not in ["ac"]:
            raise NotImplementedError(f"Aggregation on {key} is not supported.")

        # extract results.key
        data = [getattr(result, key) for result in results]

        # combine results
        df: DataFrame = pd.concat(data, axis=1)
        df = df.sum(axis=1).clip(lower=0)

        # convert to Series and return
        return df.squeeze()


@dataclass
class PVSystemManager:
    """
    Interface between the PV system model and the rest of the application. This class is responsible for
    instantiating the PV system model and running the simulation, and returning the results.

    :param config: A list of PV plant param dicts. Each entry in the list represents one entry under plant:.
    :param lat: PV system location latitude.
    :param lon: PV system location longitude.
    :param tz: PV system timezone.
    :param alt: PV system altitude.
    :param base_cec_data_path: The base path to the CEC database.
    :param inv_path: The path to the CEC inverter database.
    :param mod_path: The path to the CEC module database.
    """

    _loc: Location = field(init=False, repr=False)
    config: list[MappingProxyType[dict]]
    lat: InitVar[float] = field(repr=False)
    lon: InitVar[float] = field(repr=False)
    tz: InitVar[BaseTzInfo] = field(repr=False)
    alt: InitVar[float] = field(default=0.0, repr=False)
    inv_path: InitVar[Path] = field(default=BASE_CEC_DATA_PATH / "cec_inverters.csv", repr=False)
    mod_path: InitVar[Path] = field(default=BASE_CEC_DATA_PATH / "cec_modules.csv", repr=False)
    _pv_plants: dict[PVPlantModel] = field(init=False, repr=False)

    def __post_init__(self, lat: float, lon: float, tz: BaseTzInfo, alt: float, inv_path: Path, mod_path: Path):
        self._loc = Location(lat, lon, alt, tz, name=f"PV plant at {lat}, {lon}")
        inv_param = self._retrieve_sam_wrapper(inv_path)
        mod_param = self._retrieve_sam_wrapper(mod_path)
        self._pv_plants = self._create_pv_plants(inv_param, mod_param)

    @property
    def location(self):
        return self._loc

    def get_pv_plant(self, name: str) -> PVPlantModel:
        """Get a PV plant model by name.

        :param name: The name of the PV plant.
        :return: The PV plant model.
        """
        try:
            return self._pv_plants[name]
        except KeyError as exc:
            raise KeyError(f"PV plant {name} not found.") from exc

    def _retrieve_sam_wrapper(self, path: Path) -> pd.DataFrame:
        """Retrieve SAM database.

        :param path: The path to the SAM database.
        :return: The SAM database as a pandas DataFrame.
        """
        if not path.exists():
            raise FileNotFoundError(f"Database {path} does not exist.")

        # retrieve database
        pv_df = pvlib.pvsystem.retrieve_sam(name=None, path=str(path))
        pv_df = pv_df.transpose()
        _LOGGER.debug("Retrieved %s entries from %s.", len(pv_df), path)
        return pv_df

    def _retrieve_parameters(self, device: str, inverter: bool) -> dict:
        """Retrieve module or inverter parameters from the pvlib/SAM databases.

        :param device: The name of the module or inverter.
        :param inverter: True if the device is an inverter, False if it is a PV module.
        :return: The parameters of the device.
        """
        # retrieve parameter database
        candidates: DataFrame = self._inv_param if inverter else self._mod_param

        # check if there are duplicates
        duplicates = candidates[candidates.index.duplicated(keep=False)]
        if not duplicates.empty:
            _LOGGER.debug("Dropping %s duplicate entries.", len(duplicates))
            candidates = candidates.drop_duplicates(keep="first")

        # check if device is in the database
        try:
            params = candidates.loc[candidates.index == device].to_dict("records")[0]
            _LOGGER.debug("Found device %s in the database.", device)
        except KeyError as exc:
            raise KeyError(f"Device {device} not found in the database.") from exc

        return params

    def _create_pv_plants(self, inv_param: DataFrame, mod_param: DataFrame) -> dict[PVPlantModel]:
        """
        Create a PVPlantModel object from a user supplied config.


        :return: List of PV system model chains. One ModelChain instance for each inverter in the config.
        """
        _LOGGER.debug("Creating PV plant model.")
        pv_plants = {}
        for plant_config in self.config:
            pv_plant = PVPlantModel(
                config=plant_config,
                location=self.location,
                inv_param=inv_param,
                mod_param=mod_param,
            )
            pv_plants[plant_config["name"]] = pv_plant

        return pv_plants

    @property
    def plant_names(self) -> list[str]:
        """Return the names of the PV plants."""
        return self._pv_plants.keys()

    def run(
        self,
        name: str,
        type: ForecastType,
        weather_df: DataFrame | None = None,
        datetimes: DatetimeIndex | None = None,
    ) -> PVPlantModel:
        """Run the simulation.

        :param name: The name of the PV plant.
        :param type: The type of forecast to run.
        :param weather_df: The weather data to use for the simulation. Not required if type is ForecastType.HISTORICAL.
                           If type is ForecastType.CLEARSKY, weather_df requires only timestamps to forecast. Actual weather
                           data can be provided, but will be ignored.
        :param datetimes: The timestamps to forecast. Only required if type is ForecastType.CLEARSKY.
        :return: The PV plant model object, which contains the results of the simulation.
        """
        # check if weather data is provided
        if type is ForecastType.FORECAST and weather_df is None:
            raise ValueError(
                f"Weather data must be provided for PV forecast of type {str(ForecastType.FORECAST.name)}."
            )
        if type is ForecastType.CLEARSKY and datetimes is None:
            raise ValueError(f"Datetimes must be provided for PV forecast of type {ForecastType.CLEARSKY.name}.")

        # get PV plant
        pv_plant = self.get_pv_plant(name)

        # run simulation
        if type is ForecastType.HISTORICAL:
            pv_plant.run_historical()
        elif type is ForecastType.CLEARSKY:
            pv_plant.run_clearsky(datetimes)
        elif type is ForecastType.FORECAST:
            pv_plant.run_forecast(weather_df)
        else:
            raise ValueError(f"Forecast type {type} not supported.")

        return pv_plant
