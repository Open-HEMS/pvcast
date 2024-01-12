"""Unit tests for the model module."""
from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import Any

import polars as pl
import pytest
from pvlib.location import Location

from pvcast.model.forecasting import ForecastType
from pvcast.model.model import PVSystemManager


class TestPVModelChain:
    location = (latitude, longitude) = (52.35855344250755, 4.881086336486702)
    altitude = 10.0

    @pytest.fixture(scope="class")
    def basic_config_wrong_inv(self) -> dict[str, Any]:
        return {
            "name": "EastWest",
            "inverter": "wrong_inverter",
            "microinverter": False,
            "arrays": [
                {
                    "azimuth": 180,
                    "tilt": 30,
                    "module": "LG_Electronics_Inc__LG300N1C_B3",
                    "strings": 1,
                }
            ],
        }

    @pytest.fixture(scope="class")
    def basic_config_wrong_mod(self) -> dict[str, Any]:
        return {
            "name": "EastWest",
            "inverter": "SolarEdge_Technologies_Ltd___SE4000__240V_",
            "microinverter": False,
            "arrays": [
                {
                    "azimuth": 180,
                    "tilt": 30,
                    "module": "wrong_module",
                    "strings": 1,
                }
            ],
        }

    def test_pv_sys_mngr_init(
        self, basic_config: list[dict[str, Any]], pv_sys_mngr: PVSystemManager
    ) -> None:
        assert pv_sys_mngr.config == basic_config
        assert isinstance(pv_sys_mngr.location, Location)
        assert isinstance(pv_sys_mngr.location.latitude, float)
        assert isinstance(pv_sys_mngr.location.longitude, float)
        assert isinstance(pv_sys_mngr.location.altitude, float)
        assert pv_sys_mngr.location.tz == "UTC"
        assert set(pv_sys_mngr.plant_names) == {cfg["name"] for cfg in basic_config}

    def test_pv_sys_mngr_get_pv_plant(self, pv_sys_mngr: PVSystemManager) -> None:
        pv_sys = pv_sys_mngr.get_pv_plant("EastWest")
        assert pv_sys.name == "EastWest"
        with pytest.raises(KeyError):
            pv_sys_mngr.get_pv_plant("North")
        if len(pv_sys_mngr.pv_plants) > 1:
            pv_sys = pv_sys_mngr.get_pv_plant("South")
            assert pv_sys.name == "South"

    def test_init_pv_system_wrong_files(
        self, basic_config: list[MappingProxyType[str, Any]]
    ) -> None:
        """Test the init_pv_system function with wrong inverter param path."""
        with pytest.raises(FileNotFoundError):
            PVSystemManager(
                basic_config, *self.location, self.altitude, inv_path=Path("wrong_path")
            )

    def test_init_pv_system_wrong_inverter(
        self, basic_config_wrong_inv: list[MappingProxyType[str, Any]]
    ) -> None:
        """Test the init_pv_system function with wrong inverter model."""
        with pytest.raises(
            KeyError,
            match=f"Device {basic_config_wrong_inv['inverter']} not found in the database.",
        ):
            PVSystemManager(
                [MappingProxyType(basic_config_wrong_inv)],
                *self.location,
                self.altitude,
            )

    def test_init_pv_system_wrong_module(
        self, basic_config_wrong_mod: list[MappingProxyType[str, Any]]
    ) -> None:
        """Test the init_pv_system function with wrong module model."""
        with pytest.raises(
            KeyError, match=f"One of {set(['wrong_module'])} not found in the database."
        ):
            PVSystemManager(
                [MappingProxyType(basic_config_wrong_mod)],
                *self.location,
                self.altitude,
            )

    def test_aggregate_model_results(
        self, pv_sys_mngr: PVSystemManager, weather_df: pl.DataFrame
    ) -> None:
        pvplant = pv_sys_mngr.get_pv_plant("EastWest")
        cs_result = pvplant.clearsky.run(weather_df)
        assert cs_result.type == ForecastType.CLEARSKY
