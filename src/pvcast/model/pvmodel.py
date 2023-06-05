"""Implements a PV system model."""

import logging
from pathlib import Path
from types import MappingProxyType
from typing import Optional, Tuple

import pandas as pd
import pvlib
from pvlib.location import Location
from pvlib.modelchain import ModelChain
from pvlib.pvsystem import Array, FixedMount, PVSystem
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS

_LOGGER = logging.getLogger(__name__)


class PVModelChain:
    """Implements a PV model chain. Basically a wrapper around pvlib."""

    base_cec_data_path = Path(__file__).parent.parent / "data/proc"
    inv_path = base_cec_data_path / "cec_inverters.csv"
    mod_path = base_cec_data_path / "cec_modules.csv"

    def __init__(
        self, config: MappingProxyType, location: Tuple[float, float], altitude: float = 0.0, time_z: str = "UTC"
    ):
        """Initialize a PV system model.

        Each ModelChain object represents one PVSystem with one inverter. If the PV system uses microinverters,
        then each microinverter is represented by one ModelChain object.

        :param config: The configuration of the PV system.
        :param location: The location of the PV system.
        :param altitude: The altitude of the PV system.
        :param tz: The timezone of the PV system.
        """
        self.config = config
        self.location = Location(latitude=location[0], longitude=location[1], altitude=altitude, tz=time_z)
        self._temp_params = TEMPERATURE_MODEL_PARAMETERS["pvsyst"]["freestanding"]
        self.pv_model: list([ModelChain]) = self._create_pv_model()

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
        candidates = self._retrieve_sam_wrapper(self.inv_path if inverter else self.mod_path)

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

    def _create_pv_model(self) -> list([ModelChain]):
        """Create a PV system model from a user supplied config.

        :return: List of PV system model chains. One ModelChain instance for each inverter in the config.
        """
        pv_systems = []

        # loop over all systems
        for _, system in enumerate(self.config):
            _LOGGER.debug("Creating PV system model for system %s", system["name"])
            uses_micro: bool = system["microinverter"]
            inverter: str = system["inverter"]
            arrays: list = system["arrays"]

            # system uses microinverters, create one model chain for each PV module
            if uses_micro:
                system_models = self._build_system_micro(arrays, inverter, None)
            # system uses a single inverter, create one model chain for the whole system
            else:
                system_models = self._build_system_string(arrays, inverter, system["name"])

            # add the system models to the list of all system models
            pv_systems.append(system_models)

        return pv_systems

    def _build_system_micro(
        self, arrays: list([dict]), inverter: str, name: Optional[str] = None
    ) -> list([ModelChain]):
        """Build a PV system model for a system with microinverters.

        :param arrays: List of PV arrays.
        :param inverter: The inverter model.
        :param name: The name of the PV system.
        :return: List of PV system model chains. One ModelChain instance for each PV module.
        """
        system_models = []
        for _, array in enumerate(arrays):
            n_modules = array["strings"] * array["modules_per_string"]
            mount = FixedMount(surface_tilt=array["tilt"], surface_azimuth=array["azimuth"])

            # create a PVSystem for each microinverter
            for module_id in range(n_modules):
                module_name = f"{array['name']}_array_{module_id}"
                arr = Array(
                    mount=mount,
                    module_parameters=self._retrieve_parameters(array["module"], False),
                    temperature_model_parameters=self._temp_params,
                    strings=1,
                    modules_per_string=1,
                    name=module_name,
                )
                system_models.append(self._build_model_chain([arr], inverter, module_name if name is None else name))
        return system_models

    def _build_system_string(
        self, arrays: list([dict]), inverter: str, name: Optional[str] = "PVSystem"
    ) -> list([ModelChain]):
        """Build a PV system model for a system with a regular string inverter.

        :param arrays: List of PV arrays.
        :param inverter: The inverter model.
        :param name: The name of the PV system.
        :return: List of PV system model chains. One ModelChain instance for each PV module.
        """
        pv_arrays = []
        for array_id, array in enumerate(arrays):
            mount = FixedMount(surface_tilt=array["tilt"], surface_azimuth=array["azimuth"])
            arr = Array(
                mount=mount,
                module_parameters=self._retrieve_parameters(array["module"], False),
                temperature_model_parameters=self._temp_params,
                strings=array["strings"],
                modules_per_string=array["modules_per_string"],
                name=f"{array['name']}_array_{array_id}",
            )
            pv_arrays.append(arr)
        return [self._build_model_chain(pv_arrays, inverter, name=name)]

    def _build_model_chain(self, pv_arrays: list([Array]), inverter: str, name: str) -> ModelChain:
        # create the PV system
        pv_system = PVSystem(
            arrays=pv_arrays,
            inverter_parameters=self._retrieve_parameters(inverter, True),
            inverter=inverter,
            name=name,
        )

        # create the model chain
        modelchain = ModelChain(
            pv_system,
            self.location,
            name=name,
            aoi_model="physical",
        )

        return modelchain
