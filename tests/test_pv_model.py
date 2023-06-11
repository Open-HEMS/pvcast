from __future__ import annotations

from types import MappingProxyType

import pandas as pd
import pytest
from pvlib.location import Location
from pvlib.modelchain import ModelChain
from pvlib.pvsystem import Array, FixedMount, PVSystem
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS

from pvcast.model.pvmodelv2 import PVPlantModel, PVSystemManager


class TestPVModelChain:
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

    def test_pv_sys_mngr_init(self, basic_config):
        config = basic_config
        location = (latitude, longitude) = (10.0, 20.0)
        altitude = 100.0
        time_z = "UTC"
        pv_sys_mngr = PVSystemManager(config, *location, altitude, time_z)

        assert pv_sys_mngr.config == config
        assert pv_sys_mngr.location.latitude == latitude
        assert pv_sys_mngr.location.longitude == longitude
        assert pv_sys_mngr.location.altitude == altitude
        assert pv_sys_mngr.location.tz == time_z

    # def test_pv_model_chain_init(self, basic_config):
    #     config = basic_config
    #     location = (latitude, longitude) = (10.0, 20.0)
    #     altitude = 100.0
    #     time_z = "UTC"
    #     pv_model_chain = PVModelChain(config, location, altitude, time_z)

    #     assert pv_model_chain.config == config
    #     assert pv_model_chain.location.latitude == latitude
    #     assert pv_model_chain.location.longitude == longitude
    #     assert pv_model_chain.location.altitude == altitude
    #     assert pv_model_chain.location.tz == time_z

    # def test_create_pv_model(self, basic_config):
    #     config = basic_config
    #     location = (10.0, 20.0)
    #     altitude = 100.0
    #     time_z = "UTC"
    #     pv_model_chain = PVModelChain(config, location, altitude, time_z)
    #     pv_systems = pv_model_chain._create_pv_model()
    #     assert len(pv_systems) == 1
    #     assert isinstance(pv_systems[0][0], ModelChain)
