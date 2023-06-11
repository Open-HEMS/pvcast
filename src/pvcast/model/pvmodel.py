"""Implements a PV system model."""

from __future__ import annotations

import logging
from dataclasses import InitVar, dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import List, Optional, Tuple

import pandas as pd
import pvlib
import pytz
from pandas import DataFrame
from pvlib.location import Location
from pvlib.modelchain import ModelChain
from pvlib.pvsystem import Array, FixedMount, PVSystem
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS
from pytz import BaseTzInfo, timezone

from .const import BASE_CEC_DATA_PATH

_LOGGER = logging.getLogger(__name__)


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
    location: InitVar[Location]
    inv_param: DataFrame = field(repr=False)
    mod_param: DataFrame = field(repr=False)
    temp_param: dict = field(default_factory=lambda: TEMPERATURE_MODEL_PARAMETERS["pvsyst"]["freestanding"], repr=False)
    _pv_plant: list[ModelChain] = field(init=False, repr=False)

    def __post_init__(self, config: dict, loc: Location):
        pv_systems = self._create_pv_systems(config)
        self._pv_plant = self._build_model_chain(pv_systems, config["name"], loc)

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
    _pv_plants: list[PVPlantModel] = field(init=False, repr=False)

    def __post_init__(self, lat: float, lon: float, tz: BaseTzInfo, alt: float, inv_path: Path, mod_path: Path):
        self._loc = Location(lat, lon, alt, tz, name=f"PV plant at {lat}, {lon}")
        inv_param = self._retrieve_sam_wrapper(inv_path)
        mod_param = self._retrieve_sam_wrapper(mod_path)
        self._pv_plants = self._create_pv_plants(inv_param, mod_param)

    @property
    def location(self):
        return self._loc

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

    def _create_pv_plants(self, inv_param: DataFrame, mod_param: DataFrame) -> list[PVPlantModel]:
        """
        Create a PVPlantModel object from a user supplied config.


        :return: List of PV system model chains. One ModelChain instance for each inverter in the config.
        """
        _LOGGER.debug("Creating PV plant model.")
        pv_plants = []
        for plant_config in self.config:
            pv_plant = PVPlantModel(
                config=plant_config,
                location=self.location,
                inv_param=inv_param,
                mod_param=mod_param,
            )
            pv_plants.append(pv_plant)

        return pv_plants
