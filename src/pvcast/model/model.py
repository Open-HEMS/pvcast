"""Implements a PV system model."""

from __future__ import annotations

import logging
from dataclasses import InitVar, dataclass, field
from pathlib import Path
from types import MappingProxyType

import pandas as pd
import pvlib
from pvlib.location import Location
from pvlib.modelchain import ModelChain, ModelChainResult
from pvlib.pvsystem import Array, FixedMount, PVSystem
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS

from .const import BASE_CEC_DATA_PATH
from .forecasting import Clearsky, Forecast, Historical

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
    location: Location = field(repr=False)
    inv_param: pd.DataFrame = field(repr=False)
    mod_param: pd.DataFrame = field(repr=False)
    temp_param: dict = field(default_factory=lambda: TEMPERATURE_MODEL_PARAMETERS["pvsyst"]["freestanding"], repr=False)
    name: str = field(init=False)
    _pv_models: list[ModelChain] = field(init=False, repr=False)
    _clearsky: Clearsky = field(init=False, repr=False)
    _historical: Historical = field(init=False, repr=False)
    _forecast: Forecast = field(init=False, repr=False)

    def __post_init__(self, config: dict):
        pv_systems = self._create_pv_systems(config)
        self._pv_models = self._build_model_chain(pv_systems, self.location, config["name"])
        self.name = config["name"]

        # create the forecast objects
        self._clearsky = Clearsky(location=self.location, pv_plant=self)
        self._historical = Historical(location=self.location, pv_plant=self)
        self._forecast = Forecast(location=self.location, pv_plant=self)

    @property
    def clearsky(self):
        """The clear sky forecast result."""
        return self._clearsky

    @property
    def historical(self):
        """The historical forecast result."""
        return self._historical

    @property
    def forecast(self):
        """The live weather forecast result."""
        return self._forecast

    @property
    def models(self):
        """The PV system model chains."""
        return self._pv_models

    def _create_pv_systems(self, config: dict) -> list[PVSystem]:
        """
        Create the PV system. This method is called by __post_init__.

        In case of a PV system with microinverters, each microinverter is represented by one PVSystem object.
        """
        _LOGGER.debug("Creating PV system model for system %s", config["name"])
        micro: bool = bool(config["microinverter"].lower() == "true")
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
        _LOGGER.debug("Building microinverter system model for system %s", name)
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
        _LOGGER.debug("Building string inverter system model for system %s", name)
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

        # check if there are duplicates in the index and remove them
        candidates = candidates[~candidates.index.duplicated(keep="first")]

        # check if device is in the database
        try:
            params = candidates.loc[device].to_dict()
            _LOGGER.debug("Found params %s for device %s in the database.", params, device)
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

    def aggregate(self, results: list[ModelChainResult], key: str) -> pd.Series:
        """Aggregate the results of the model chains into a single pd.DataFrame.

        :param results: List of model chain result objects.
        :param key: The key to aggregate on. Can be "ac", "dc", ..., but currently only "ac" is supported.
        :return: The aggregated results.
        """
        # extract results.key
        data = [getattr(result, key) for result in results]

        # combine results
        data: pd.DataFrame = pd.concat(data, axis=1)
        data = data.sum(axis=1).clip(lower=0)

        # convert to pd.Series and return
        return data.squeeze()


@dataclass
class PVSystemManager:
    """Interface between the PV system model and the rest of the application.
    This class is responsible for instantiating the PV system model and running the simulation,
    and returning the results. Everything in PVModel is done in UTC timezone.

    :param config: A list of PV plant param dicts. Each entry in the list represents one entry under plant:.
    :param lat: PV system location latitude.
    :param lon: PV system location longitude.
    :param alt: PV system altitude.
    :param base_cec_data_path: The base path to the CEC database.
    :param inv_path: The path to the CEC inverter database.
    :param mod_path: The path to the CEC module database.
    """

    _loc: Location = field(init=False, repr=False)
    config: list[MappingProxyType[dict]]
    lat: InitVar[float] = field(repr=False)
    lon: InitVar[float] = field(repr=False)
    alt: InitVar[float] = field(default=0.0, repr=False)
    inv_path: InitVar[Path] = field(default=BASE_CEC_DATA_PATH / "cec_inverters.csv", repr=False)
    mod_path: InitVar[Path] = field(default=BASE_CEC_DATA_PATH / "cec_modules.csv", repr=False)
    _pv_plants: dict[PVPlantModel] = field(init=False, repr=False)

    def __post_init__(self, lat: float, lon: float, alt: float, inv_path: Path, mod_path: Path):
        self._loc = Location(lat, lon, tz="UTC", altitude=alt, name=f"PV plant at {lat}, {lon}")
        inv_param = self._retrieve_sam_wrapper(inv_path)
        mod_param = self._retrieve_sam_wrapper(mod_path)
        self._pv_plants = self._create_pv_plants(inv_param, mod_param)

    @property
    def location(self):
        """Location of the PV system encoded as a PVLib Location object."""
        return self._loc

    @property
    def pv_plants(self):
        """The PV plants."""
        return self._pv_plants

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
        :return: The SAM database as a pandas pd.DataFrame.
        """
        _LOGGER.debug("Retrieving SAM database from %s.", path)
        if not path.exists():
            raise FileNotFoundError(f"Database {path} does not exist.")

        # retrieve database
        pv_df = pvlib.pvsystem.retrieve_sam(name=None, path=str(path))
        pv_df = pv_df.transpose()
        _LOGGER.debug("Retrieved %s SAM database entries from %s.", len(pv_df), path)
        return pv_df

    def _create_pv_plants(self, inv_param: pd.DataFrame, mod_param: pd.DataFrame) -> dict[PVPlantModel]:
        """Create a PVPlantModel object from a user supplied config.

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
