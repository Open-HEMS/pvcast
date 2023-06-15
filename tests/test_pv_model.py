from __future__ import annotations

from types import MappingProxyType

import pandas as pd
import pytest
from pvlib.location import Location
from pvlib.modelchain import ModelChain
from pvlib.pvsystem import Array, FixedMount, PVSystem
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS

from pvcast.model.pvmodel import ForecastType, PVPlantModel, PVSystemManager


class TestPVModelChain:
    location = (latitude, longitude) = (10.0, 20.0)
    altitude = 100.0
    time_z = "Europe/Amsterdam"

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
        return PVSystemManager(basic_config, *self.location, self.altitude, self.time_z)

    def test_pv_sys_mngr_init(self, basic_config, pv_sys_mngr: PVSystemManager):
        assert pv_sys_mngr.config == basic_config
        assert pv_sys_mngr.location.latitude == self.latitude
        assert pv_sys_mngr.location.longitude == self.longitude
        assert pv_sys_mngr.location.altitude == self.altitude
        assert pv_sys_mngr.location.tz == self.time_z
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

    def test_pv_sys_mngr_run(self, pv_sys_mngr: PVSystemManager):
        # start and end dates for clearsky forecast
        start_date = pd.Timestamp("2015-06-01")
        end_date = pd.Timestamp("2015-06-02")
        datetimes = pd.date_range(start_date, end_date, freq="1h", tz=self.time_z)

        # run clearsky forecast
        pv_plant = pv_sys_mngr.run(name="EastWest", type=ForecastType.CLEARSKY, datetimes=datetimes)
        assert isinstance(pv_plant.clearsky, pd.Series)
        assert pv_plant.clearsky.index.equals(datetimes)
        assert pv_plant.name == "EastWest"
