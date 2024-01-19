"""Implements a PV system model."""

from __future__ import annotations

import logging
from dataclasses import InitVar, dataclass, field
from typing import TYPE_CHECKING, Any

import polars as pl
from pvlib.location import Location
from pvlib.modelchain import ModelChain
from pvlib.pvsystem import Array, FixedMount, PVSystem
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS

from .const import BASE_CEC_DATA_PATH
from .forecasting import Clearsky, Historical, Live

if TYPE_CHECKING:
    from pathlib import Path
    from types import MappingProxyType

_LOGGER = logging.getLogger(__name__)


@dataclass
class PVPlantModel:
    """Implements the entire PV model chain based on the parameters set in config.yaml.

    This class is basically a wrapper around pvlib. Each entry in the plant list in config.yaml file should be instantiated as a PVModelChain object.
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

    config: InitVar[MappingProxyType[str, Any]]
    location: Location = field(repr=False)
    inv_param: InitVar[pl.LazyFrame]
    mod_param: InitVar[pl.LazyFrame]
    temp_param: dict[str, dict[str, dict[str, Any]]] = field(
        default_factory=lambda: TEMPERATURE_MODEL_PARAMETERS["pvsyst"]["freestanding"],
        repr=False,
    )
    name: str = field(init=False)
    _pv_models: list[ModelChain] = field(init=False, repr=False)
    _clearsky: Clearsky = field(init=False, repr=False)
    _historical: Historical = field(init=False, repr=False)
    _live: Live = field(init=False, repr=False)

    def __post_init__(
        self,
        config: MappingProxyType[str, Any],
        inv_param: pl.LazyFrame,
        mod_param: pl.LazyFrame,
    ) -> None:
        """Perform post-initialization tasks for the PVPlantModel.

        This method creates the PV system models, sets the name, and initializes the forecast objects.

        :param config: The PV plant configuration dictionary.
        :param inv_param: The inverter parameters.
        :param mod_param: The module parameters.
        """
        pv_systems = self._create_pv_systems(config, inv_param, mod_param)
        self._pv_models = [
            ModelChain(system, self.location, name=config["name"], aoi_model="physical")
            for system in pv_systems
        ]
        self.name = config["name"]

        # create the forecast objects
        self._clearsky = Clearsky(location=self.location, pv_plant=self)
        self._historical = Historical(location=self.location, pv_plant=self)
        self._live = Live(location=self.location, pv_plant=self)

    @property
    def clearsky(self) -> Clearsky:
        """The clear sky forecast result."""
        return self._clearsky

    @property
    def historical(self) -> Historical:
        """The historical forecast result."""
        return self._historical

    @property
    def live(self) -> Live:
        """The live weather forecast result."""
        return self._live

    @property
    def models(self) -> list[ModelChain]:
        """The PV system model chains."""
        return self._pv_models

    def _create_pv_systems(
        self,
        config: MappingProxyType[str, Any],
        inv_param: pl.LazyFrame,
        mod_param: pl.LazyFrame,
    ) -> list[PVSystem]:
        """Create the PV system. This method is called by __post_init__.

        In case of a PV system with microinverters, each microinverter is represented by one PVSystem object.
        """
        _LOGGER.debug("Creating PV system model for system %s", config["name"])
        micro: bool = config["microinverter"]
        arrays: list[dict[str, str | int]] = config["arrays"]

        # get inverter params from the SAM database
        inv_df: pl.DataFrame = inv_param.filter(index=config["inverter"]).collect()
        if inv_df.is_empty():
            msg = f"Device {config["inverter"]} not found in the database."
            raise KeyError(msg)
        inv_dict = dict(inv_df.rows_by_key(key=["index"], named=True, unique=True))

        # get module params from the SAM database
        modules = pl.Series([array["module"] for array in arrays]).unique()  # pylint: disable=assignment-from-no-return
        mod_df: pl.DataFrame = mod_param.filter(index=modules).collect()

        if len(modules) != len(mod_df):
            found_modules = set(mod_df["index"])
            not_found = set(modules) - found_modules
            msg = f"One of {not_found} not found in the database."
            raise KeyError(msg)

        mod_dict = dict(mod_df.rows_by_key(key=["index"], named=True, unique=True))

        # system uses microinverters, create one model chain for each PV module
        if micro:
            pv_systems = self._build_system_micro(
                arrays, inv_param=inv_dict, mod_param=mod_dict, name=config["name"]
            )

        # system uses a single inverter, create one model chain for the whole system
        else:
            pv_systems = self._build_system_string(
                arrays, inv_param=inv_dict, mod_param=mod_dict, name=config["name"]
            )
        return pv_systems

    def _build_system_micro(
        self,
        arrays: list[dict[str, str | int]],
        inv_param: dict[str, dict[str, Any]],
        mod_param: dict[str, dict[str, Any]],
        name: str | None = None,
    ) -> list[PVSystem]:
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
            n_modules = int(array["strings"]) * int(array["modules_per_string"])
            mount = FixedMount(
                surface_tilt=array["tilt"], surface_azimuth=array["azimuth"]
            )
            module_param = mod_param[array["module"]]  # type: ignore[index]

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
                    inverter_parameters=next(iter(inv_param.values())),
                    name=name,
                )
                pv_systems.append(pv_system)

        return pv_systems

    def _build_system_string(
        self,
        arrays: list[dict[str, str | int]],
        inv_param: dict[str, dict[str, Any]],
        mod_param: dict[str, dict[str, Any]],
        name: str | None = None,
    ) -> list[PVSystem]:
        """Build a PV system model for a system with a regular string inverter.

        :param arrays: List of PV arrays.
        :param inv_param: The inverter model parameters:
                           {inverter_name: {param_name: param_value}}.
        :param mod_param: The module model parameters:
                           {module_name: {param_name: param_value}}.
        :param name: The name of the PV system.
        :return: List of PV system model chains.
        """
        _LOGGER.debug("Building string inverter system model for system %s", name)
        pv_arrays = []

        # a string system uses one inverter so we aggregate all arrays into one PVSystem
        for array_id, array in enumerate(arrays):
            mount = FixedMount(
                surface_tilt=array["tilt"], surface_azimuth=array["azimuth"]
            )
            module_param = mod_param[array["module"]]  # type: ignore[index]

            # define PV array
            arr = Array(
                mount=mount,
                module=array["module"],
                module_parameters=module_param,
                temperature_model_parameters=self.temp_param,
                strings=array["strings"],
                modules_per_string=array["modules_per_string"],
                name=f"{array['name']}_array_{array_id}",
            )
            pv_arrays.append(arr)

        # create the PV system
        pv_system = PVSystem(
            arrays=pv_arrays,
            inverter=next(iter(inv_param.keys())),
            inverter_parameters=next(iter(inv_param.values())),
            name=name,
        )
        return [pv_system]


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
    config: list[MappingProxyType[str, Any]]
    lat: InitVar[float] = field(repr=False)
    lon: InitVar[float] = field(repr=False)
    alt: InitVar[float] = field(default=0.0, repr=False)
    inv_path: InitVar[Path] = field(
        default=BASE_CEC_DATA_PATH / "cec_inverters.csv", repr=False
    )
    mod_path: InitVar[Path] = field(
        default=BASE_CEC_DATA_PATH / "cec_modules.csv", repr=False
    )
    _pv_plants: dict[str, PVPlantModel] = field(init=False, repr=False)

    def __post_init__(  # pylint: disable=too-many-arguments
        self, lat: float, lon: float, alt: float, inv_path: Path, mod_path: Path
    ) -> None:
        """Perform post-initialization tasks for the PVSystemManager."""
        self._loc = Location(
            lat, lon, tz="UTC", altitude=alt, name=f"PV plant at {lat}, {lon}"
        )

        # load the CEC databases as polars LazyFrames which can
        inv_param: pl.LazyFrame = pl.scan_csv(inv_path)
        mod_param: pl.LazyFrame = pl.scan_csv(mod_path)
        self._pv_plants = self._create_pv_plants(inv_param, mod_param)
        _LOGGER.info(
            "Created PV system manager with %s PV plants.", len(self._pv_plants)
        )

    @property
    def location(self) -> Location:
        """Location of the PV system encoded as a PVLib Location object."""
        return self._loc

    @property
    def pv_plants(self) -> dict[str, PVPlantModel]:
        """The PV plants."""
        return self._pv_plants

    @property
    def pv_plant_count(self) -> int:
        """The number of PV plants."""
        return len(self._pv_plants)

    def get_pv_plant(self, name: str) -> PVPlantModel:
        """Get a PV plant model by name.

        :param name: The name of the PV plant.
        :return: The PV plant model.
        """
        try:
            return self._pv_plants[name]
        except KeyError as exc:
            msg = f"PV plant {name} not found."
            raise KeyError(msg) from exc

    def _create_pv_plants(
        self, inv_param: pl.LazyFrame, mod_param: pl.LazyFrame
    ) -> dict[str, PVPlantModel]:
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
        return list(self._pv_plants.keys())
