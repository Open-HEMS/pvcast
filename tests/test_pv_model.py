from __future__ import annotations

from types import MappingProxyType

import pandas as pd
import pytest
from pandas import infer_freq
from pvlib.location import Location
from pvlib.modelchain import ModelChain
from pvlib.pvsystem import Array, FixedMount, PVSystem
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS

from pvcast.model.pvmodel import ForecastType, PVPlantModel, PVSystemManager


class TestPVModelChain:
    location = (latitude, longitude) = (52.35855344250755, 4.881086336486702)
    altitude = 10.0
    time_z = "Europe/Amsterdam"
    start_date = pd.Timestamp("2015-06-01")
    end_date = pd.Timestamp("2015-07-01")
    freq = pd.to_timedelta("1h")
    datetimes = pd.date_range(start_date, end_date - freq, freq=freq, tz=time_z)

    @pytest.fixture()
    def time_aliases(self, pd_time_aliases):
        return pd_time_aliases

    @pytest.fixture
    def basic_config(self):
        return [
            MappingProxyType(
                {
                    "name": "EastWest",
                    "inverter": "SolarEdge_Technologies_Ltd___SE4000__240V_",
                    "microinverter": "false",
                    "arrays": [
                        {
                            "name": "East",
                            "tilt": 30,
                            "azimuth": 90,
                            "modules_per_string": 4,
                            "strings": 1,
                            "module": "Trina_Solar_TSM_330DD14A_II_",
                        },
                        {
                            "name": "West",
                            "tilt": 30,
                            "azimuth": 270,
                            "modules_per_string": 8,
                            "strings": 1,
                            "module": "Trina_Solar_TSM_330DD14A_II_",
                        },
                    ],
                }
            ),
            MappingProxyType(
                {
                    "name": "South",
                    "inverter": "SolarEdge_Technologies_Ltd___SE4000__240V_",
                    "microinverter": "false",
                    "arrays": [
                        {
                            "name": "South",
                            "tilt": 30,
                            "azimuth": 180,
                            "modules_per_string": 8,
                            "strings": 1,
                            "module": "Trina_Solar_TSM_330DD14A_II_",
                        }
                    ],
                }
            ),
        ]

    @pytest.fixture
    def pv_sys_mngr(self, basic_config):
        return PVSystemManager(basic_config, *self.location, self.altitude)

    @pytest.fixture
    def pvplant_clearsky(self, pv_sys_mngr: PVSystemManager):
        pv_plant = pv_sys_mngr.run(name="EastWest", fc_type=ForecastType.CLEARSKY, datetimes=self.datetimes)
        return pv_plant

    @pytest.fixture
    def pvplant_historical(self, pv_sys_mngr: PVSystemManager):
        pv_plant = pv_sys_mngr.run(name="EastWest", fc_type=ForecastType.HISTORICAL)
        return pv_plant

    @pytest.fixture(params=["A", "M", "1W", "1D", "1H"])
    def freq(self, request):
        return request.param

    def test_pv_sys_mngr_init(self, basic_config, pv_sys_mngr: PVSystemManager):
        assert pv_sys_mngr.config == basic_config
        assert pv_sys_mngr.location.latitude == self.latitude
        assert pv_sys_mngr.location.longitude == self.longitude
        assert pv_sys_mngr.location.altitude == self.altitude
        assert pv_sys_mngr.location.tz == "UTC"
        assert isinstance(pv_sys_mngr.location, Location)
        assert set(pv_sys_mngr.plant_names) == {cfg["name"] for cfg in basic_config}

    def test_pv_sys_mngr_get_pv_plant(self, pv_sys_mngr: PVSystemManager):
        pv_sys = pv_sys_mngr.get_pv_plant("EastWest")
        assert isinstance(pv_sys, PVPlantModel)
        assert pv_sys.name == "EastWest"

        pv_sys = pv_sys_mngr.get_pv_plant("South")
        assert isinstance(pv_sys, PVPlantModel)
        assert pv_sys.name == "South"

        with pytest.raises(KeyError):
            pv_sys_mngr.get_pv_plant("North")

    def test_pv_sys_mngr_clearsky(self, pvplant_clearsky: PVPlantModel):
        assert isinstance(pvplant_clearsky.clearsky.ac_power, pd.Series)
        assert pvplant_clearsky.clearsky.type == ForecastType.CLEARSKY
        assert (pvplant_clearsky.clearsky.ac_power >= 0.0).all(), "Clearsky forecast should be non-negative"
        assert pvplant_clearsky.clearsky.ac_power.index.equals(self.datetimes)
        assert pvplant_clearsky.name == "EastWest"
        assert pvplant_clearsky.clearsky.type == ForecastType.CLEARSKY

    def test_pv_plant_result_resample(self, pvplant_clearsky: PVPlantModel, time_aliases):
        # resample to 30min
        resampled_result = pvplant_clearsky.clearsky.resample("30Min")
        assert resampled_result.freq == "30Min"
        assert infer_freq(resampled_result.ac_power.index) in time_aliases["30Min"]

    def test_pv_sys_mngr_historic(self, pvplant_historical: PVPlantModel):
        assert isinstance(pvplant_historical.historic.ac_power, pd.Series)
        assert pvplant_historical.historic.type == ForecastType.HISTORICAL
        assert (pvplant_historical.historic.ac_power >= 0.0).all(), "Historic forecast should be non-negative"

    def test_historic_resample(self, pvplant_historical: PVPlantModel):
        # resample to monthly
        resampled_result = pvplant_historical.historic.resample("M")
        assert resampled_result.freq == "M"
        assert resampled_result.ac_power.index.freq == "M"

    def test_historic_energy(self, pvplant_historical: PVPlantModel, freq):
        energy_result = pvplant_historical.historic.energy(freq=freq)
        assert energy_result.freq == "1H"  # original power data freq does not change
        assert energy_result.ac_energy.index.freq == freq

    def test_clearsky_energy(self, pvplant_clearsky: PVPlantModel, freq):
        energy_result = pvplant_clearsky.clearsky.energy(freq=freq)
        assert energy_result.ac_energy.index.freq == freq
