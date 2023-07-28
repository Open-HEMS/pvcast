"""Implements a PV system model."""

from __future__ import annotations

import copy
import logging
from dataclasses import InitVar, dataclass, field
from enum import Enum
from pathlib import Path
from types import MappingProxyType

import pandas as pd
import pvlib
from pvlib.iotools import get_pvgis_tmy
from pvlib.location import Location
from pvlib.modelchain import ModelChain, ModelChainResult
from pvlib.pvsystem import Array, FixedMount, PVSystem
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS

from .const import BASE_CEC_DATA_PATH

_LOGGER = logging.getLogger(__name__)


class ForecastType(str, Enum):
    """Enum for the type of PVPlantResults."""

    LIVE = "live"
    CLEARSKY = "clearsky"
    HISTORICAL = "historic"


@dataclass
class PVPlantResult:
    """Object to store the aggregated results of the PVPlantModel simulation.

    :param name: The name of the PV plant.
    :param type: The type of the result: forecast based on weather data, clearsky, or historic based on PVGIS.
    :param ac_power: The sum of AC power outputs of all ModelChain objects in the PV plant.
    :param dc_power: If available, DC power broken down into individual arrays. Each array is a column in the pd.DataFrame.
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
    _freqs: tuple[str] = field(repr=False, init=False, default=("A", "M", "1W", "1D", "1H", "30Min", "15Min"))

    def __post_init__(self):
        """Post-initialization function."""
        if self.ac_power is not None and self.ac_power.index.freq is None:
            self.ac_power.index = self._add_freq(self.ac_power.index)

    def resample(self, freq: str, interp_method: str = "linear") -> PVPlantResult:
        """Resample the entire PVPlantResult to a new interval.

        :param freq: The frequency of the energy output. See pandas.resample() for valid options.
        :param interp_method: The interpolation method to use. Any option of pd.interpolate() is valid.
        :return: A new PVPlantResult object with the resampled data.
        """
        if freq not in self._freqs:
            raise ValueError(f"Frequency {freq} not supported. Must be one of {self._freqs}.")
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
        if self._freqs.index(freq) > self._freqs.index("1H"):
            raise ValueError(
                "For forecast with future weather data energy can only be calculated up to hourly interval."
            )
        if self._freqs.index(freq) > self._freqs.index(self.freq):
            raise ValueError(
                f"Cannot calculate energy for a frequency higher than the fundamental data frequency ({self.freq})."
            )

        # resample to hourly frequency and then sum to get Wh
        plant_cpy = self.resample("1H")
        ac_energy = plant_cpy.ac_power.resample(freq).sum()
        return ac_energy


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
    _pv_plant: list[ModelChain] = field(init=False, repr=False)
    name: str = field(init=False)
    _live: PVPlantResult | None = field(init=False, repr=False, default=None)
    _clearsky: PVPlantResult | None = field(init=False, repr=False, default=None)
    _historical: PVPlantResult | None = field(init=False, repr=False, default=None)
    pvgis_data_path: Path = field(init=False, repr=False, default=None)

    def __post_init__(self, config: dict):
        pv_systems = self._create_pv_systems(config)
        self._pv_plant = self._build_model_chain(pv_systems, self.location, config["name"])
        self.name = config["name"]
        lat = str(round(self.location.latitude, 4)).replace(".", "_")
        lon = str(round(self.location.longitude, 4)).replace(".", "_")
        # set a default path for the pvgis data if not provided
        if self.pvgis_data_path is None:
            self.pvgis_data_path = Path(f"src/pvcast/data/pvgis/pvgis_tmy_{lat}_{lon}.csv")

    @property
    def live(self) -> PVPlantResult | None:
        """Return the forecast results of the PV plant."""
        return self._live

    @property
    def clearsky(self) -> PVPlantResult | None:
        """Return the clearsky results of the PV plant."""
        return self._clearsky

    @property
    def historic(self) -> PVPlantResult | None:
        """Return the historic results of the PV plant."""
        return self._historical

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

    def run_live(self, weather_df: pd.DataFrame, pvgis=False) -> None:
        """Run the forecast for the PV system with the given (live) weather data.

        :param weather_df: The weather forecast pd.DataFrame.
        :param pvgis: True if the forecast is for historical pvgis data, False if it is for future data.
        """
        # run the forecast for each model chain
        results = []
        for model_chain in self._pv_plant:
            model_chain.run_model(weather_df)
            results.append(model_chain.results)

        # combine the results
        ac_power = self._aggregate(results, "ac")
        result = PVPlantResult(
            name=self.name,
            type=ForecastType.HISTORICAL if pvgis else ForecastType.LIVE,
            ac_power=ac_power,
            dc_power=None,
            modelresults=results,
            weather=weather_df,
        )

        if pvgis:
            self._historical = result
        else:
            self._live = result

    def run_clearsky(self, weather_df: pd.DataFrame) -> None:
        """Run the forecast for the PV system based on clear sky weather data obtained from the location object.

        :param weather_df: Weather pd.DataFrame. Weather columns, if present, will be ignored, only the index is used.
        """
        # get clear sky weather data
        weather_df = self.location.get_clearsky(weather_df.index)

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
        ac_power = self._aggregate(results, "ac")
        self._clearsky = PVPlantResult(
            name=self.name,
            type=ForecastType.CLEARSKY,
            ac_power=ac_power,
            dc_power=None,
            modelresults=results,
            weather=weather_df,
        )

    def run_historical(self) -> None:
        """Run simulation for the PV system based on TMY historical weather data obtained from PVGIS."""
        tmy_data = self._get_pvgis_data()

        # re-index the data so that datetimes are consecutive
        tmy_data.index = pd.date_range(start="2021-01-01 00:00", end="2021-12-31 23:00", freq="1H")

        # run the forecast for each model chain
        self.run_live(tmy_data, pvgis=True)

    def _get_pvgis_data(self, save_data: bool = True, force_api: bool = False) -> pd.DataFrame:
        """
        Retrieve the PVGIS data using the PVGIS API. Returned data should include the following columns:
        [temp_air, relative_humidity, ghi, dni, dhi, wind_speed]. Other columns are ignored.

        If the path is provided, columnnames of the supplied CSV file must follow the same naming convention.

        :param path: The path to the PVGIS data file in CSV format. If None, the data is retrieved using the PVGIS API.
        :param save_data: If True, data retrieved from the API is saved to the path so it can be reused later.
        :return: PVGIS pd.DataFrame.
        """
        from_file = self.pvgis_data_path.exists() and not force_api
        if from_file:
            # read data from CSV file
            _LOGGER.debug("Reading PVGIS data from file at: %s.", self.pvgis_data_path)
            tmy_data = pd.read_csv(self.pvgis_data_path, index_col=0, parse_dates=True, header=0)
        else:
            _LOGGER.debug("Retrieving PVGIS data from API.")
            # create parent directory
            self.pvgis_data_path.parent.mkdir(parents=True, exist_ok=True)

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
        if "precipitable_water" not in tmy_data.columns:
            tmy_data["precipitable_water"] = pvlib.atmosphere.gueymard94_pw(
                tmy_data["temp_air"], tmy_data["relative_humidity"]
            )

        # save data to CSV file if it was retrieved from the API
        if not from_file and save_data:
            tmy_data.to_csv(self.pvgis_data_path)
        return tmy_data

    def _aggregate(self, results: list[ModelChainResult], key: str) -> pd.Series:
        """Aggregate the results of the model chains into a single pd.DataFrame.

        :param results: List of model chain result objects.
        :param key: The key to aggregate on. Can be "ac", "dc", ..., but currently only "ac" is supported.
        :return: The aggregated results.
        """
        # extract results.key
        data = [getattr(result, key) for result in results]

        # combine results
        df: pd.DataFrame = pd.concat(data, axis=1)
        df = df.sum(axis=1).clip(lower=0)

        # convert to pd.Series and return
        return df.squeeze()


@dataclass
class PVSystemManager:
    """
    Interface between the PV system model and the rest of the application. This class is responsible for
    instantiating the PV system model and running the simulation, and returning the results.

    Everything in PVModel is done in UTC timezone.

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
        fc_type: ForecastType,
        weather_df: pd.DataFrame | None = None,
    ) -> PVPlantModel:
        """Run the simulation.

        :param name: The name of the PV plant.
        :param type: The type of forecast to run.
        :param weather_df: The weather data to use for the simulation. Not required if type is ForecastType.HISTORICAL.
                           If type is ForecastType.CLEARSKY, weather_df requires only pd.Timestamps to forecast. Actual
                           weather data can be provided, but will be ignored.
        :return: The PV plant model object, which contains the results of the simulation.
        """
        # check if weather data is provided
        if (fc_type is ForecastType.LIVE or ForecastType.CLEARSKY) and weather_df is None:
            raise ValueError(f"Weather data must be provided for PV forecast of type: {fc_type}.")

        # add preciptable_water to weather_df if it is not in the weather data already
        weather_df.rename(columns={"temperature": "temp_air", "humidity": "relative_humidity"}, inplace=True)
        if "precipitable_water" not in weather_df.columns:
            weather_df["precipitable_water"] = pvlib.atmosphere.gueymard94_pw(
                weather_df["temp_air"], weather_df["relative_humidity"]
            )

        # get PV plant
        pv_plant = self.get_pv_plant(name)

        # run simulation
        if fc_type is ForecastType.HISTORICAL:
            pv_plant.run_historical()
        elif fc_type is ForecastType.CLEARSKY:
            pv_plant.run_clearsky(weather_df)
        elif fc_type is ForecastType.LIVE:
            pv_plant.run_live(weather_df)
        else:
            raise ValueError(f"Forecast type {fc_type} not supported.")

        return pv_plant
