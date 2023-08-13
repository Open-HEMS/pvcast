from __future__ import annotations

from pathlib import Path
from types import MappingProxyType

import numpy as np
import pandas as pd
import pytest
from pvlib.location import Location

from pvcast.model.model import (ForecastType, PVPlantModel, PVPlantResult,
                                PVSystemManager)


class TestPVModelChain:
    location = (latitude, longitude) = (52.35855344250755, 4.881086336486702)
    altitude = 10.0
    time_z = "Europe/Amsterdam"
    start_date = pd.Timestamp("2015-06-01")
    end_date = pd.Timestamp("2015-07-01")
    freq = pd.to_timedelta("1h")

    string_system = [
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

    micro_system = [
        MappingProxyType(
            {
                "name": "EastWest",
                "inverter": "Enphase_Energy_Inc___IQ7X_96_x_ACM_US__240V_",
                "microinverter": "true",
                "arrays": [
                    {
                        "name": "zone_1_schuin",
                        "tilt": 30,
                        "azimuth": 90,
                        "modules_per_string": 5,
                        "strings": 1,
                        "module": "JA_Solar_JAM72S01_385_PR",
                    },
                    {
                        "name": "zone_2_plat",
                        "tilt": 15,
                        "azimuth": 160,
                        "modules_per_string": 8,
                        "strings": 1,
                        "module": "JA_Solar_JAM72S01_385_PR",
                    },
                ],
            }
        )
    ]

    @pytest.fixture(scope="class")
    def time_aliases(self, pd_time_aliases):
        return pd_time_aliases

    @pytest.fixture(scope="class", params=[string_system, micro_system])
    def basic_config(self, request):
        return request.param

    @pytest.fixture(scope="class")
    def pv_sys_mngr(self, basic_config):
        return PVSystemManager(basic_config, *self.location, self.altitude)

    @pytest.fixture(scope="class")
    def pv_sys_mngr_wrong_inv_path(self, basic_config):
        return PVSystemManager(basic_config, *self.location, self.altitude, inv_path=Path("wrong_path"))

    @pytest.fixture(params=["A", "M", "1W", "1D", "1H", "30Min", "15Min"], scope="class")
    def freq(self, request):
        return request.param

    @pytest.fixture(
        params=[
            ForecastType.CLEARSKY,
            pytest.param(ForecastType.HISTORICAL, marks=pytest.mark.remote_data),
            ForecastType.LIVE,
        ],
        scope="class",
    )
    def fc_type(self, request):
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
        with pytest.raises(KeyError):
            pv_sys_mngr.get_pv_plant("North")
        if len(pv_sys_mngr.pv_plants) > 1:
            pv_sys = pv_sys_mngr.get_pv_plant("South")
            assert isinstance(pv_sys, PVPlantModel)
            assert pv_sys.name == "South"

    def test_resample(self, pv_sys_mngr, fc_type, freq, weather_df):
        pvplant = pv_sys_mngr.run(name="EastWest", fc_type=fc_type, weather_df=weather_df)
        resampled_result = getattr(pvplant, fc_type.value.lower()).resample(freq)
        assert resampled_result.freq == freq
        assert resampled_result.ac_power.index.freq == freq

    def test_resample_wrong_freq(self, pv_sys_mngr: PVSystemManager, weather_df):
        pvplant_clearsky = pv_sys_mngr.run(name="EastWest", fc_type=ForecastType.CLEARSKY, weather_df=weather_df)
        with pytest.raises(ValueError):
            pvplant_clearsky.clearsky.resample("wrong_freq")

    def test_energy_calculation(self, pv_sys_mngr, fc_type, freq, weather_df):
        pv_plant = pv_sys_mngr.run(name="EastWest", fc_type=fc_type, weather_df=weather_df)
        if freq in ["30Min", "15Min"]:
            with pytest.raises(ValueError):
                energy_result = getattr(pv_plant, fc_type.value.lower()).energy(freq=freq)
        else:
            orig_result = getattr(pv_plant, fc_type.value.lower())
            energy_result = getattr(pv_plant, fc_type.value.lower()).energy(freq=freq)
            assert isinstance(energy_result, pd.Series)
            assert orig_result.ac_power.index.freq == "1H"
            assert energy_result.index.freq == freq
            assert len(energy_result) == len(energy_result.resample(freq).sum())
            assert energy_result.sum() > 0.0
            assert energy_result.sum() == pytest.approx(orig_result.ac_power.sum(), rel=1e-3)

    def test_energy_calculation_no_ac_power(self, fc_type, freq):
        pv_plant_result = PVPlantResult(name="test", type=fc_type)
        with pytest.raises(ValueError):
            pv_plant_result.energy(freq=freq)

    def test_energy_calculation_too_high_freq(self, pv_sys_mngr: PVSystemManager, weather_df):
        pvplant_clearsky = pv_sys_mngr.run(name="EastWest", fc_type=ForecastType.CLEARSKY, weather_df=weather_df)
        resampled_result = pvplant_clearsky.clearsky.resample("1D")
        with pytest.raises(ValueError):
            resampled_result.energy(freq="1H")

    @pytest.mark.parametrize("freq_opt, freq", [(None, "30T"), ("30T", None), ("30T", "30T")])
    def test_add_freq(self, freq_opt: str | None, freq: str | None):
        """Test the add_freq function."""
        index = pd.DatetimeIndex(
            ["2020-01-01 00:00:00", "2020-01-01 00:30:00", "2020-01-01 01:00:00"], tz="UTC", freq=freq_opt
        )
        pv_plant_result = PVPlantResult(
            name="test", ac_power=pd.Series([1, 2, 3], index=index), type=ForecastType.HISTORICAL
        )
        result = pv_plant_result._add_freq(index, freq)
        assert result.freq == "30T"

    def test_add_freq_wrong_index(self, fc_type):
        """Test the add_freq function with wrong index."""
        index = pd.DatetimeIndex(["2020-01-01 00:00:00", "2020-01-01 00:10:00", "2020-01-01 01:00:00"], tz="UTC")
        with pytest.raises(AttributeError):
            pv_plant_result = PVPlantResult(name="test", ac_power=pd.Series([1, 2, 3], index=index), type=fc_type)

    def test_init_pv_system_wrong_files(self, basic_config):
        """Test the init_pv_system function with wrong inverter param path."""
        with pytest.raises(FileNotFoundError):
            PVSystemManager(basic_config, *self.location, self.altitude, inv_path=Path("wrong_path"))

    def test_pv_system_run_no_weather_df(self, basic_config, fc_type):
        """Test the init_pv_system run function without providing weather_df."""

        # skip for historical forecast
        if fc_type == ForecastType.HISTORICAL:
            pytest.skip("Skip for historical forecast as they do not use weather_df.")

        pv_sys_mngr = PVSystemManager(basic_config, *self.location, self.altitude)
        with pytest.raises(ValueError):
            pv_sys_mngr.run(name="EastWest", fc_type=ForecastType.LIVE)

    def test_pv_system_run_inc_precipitable_water(self, basic_config, fc_type, weather_df):
        """Test the init_pv_system run function with precipitable water."""
        # skip for historical forecast
        if fc_type == ForecastType.HISTORICAL:
            pytest.skip("Skip for historical forecast as they do not use weather_df.")
        weather_df["precipitable_water"] = np.random.uniform(0.1, 1.0, len(weather_df))
        pv_sys_mngr = PVSystemManager(basic_config, *self.location, self.altitude)
        pv_sys_mngr.run(name="EastWest", fc_type=fc_type, weather_df=weather_df)

    def test_pv_system_run_wrong_fc_type(self, basic_config, weather_df):
        """Test the init_pv_system run function with wrong fc_type."""
        pv_sys_mngr = PVSystemManager(basic_config, *self.location, self.altitude)
        with pytest.raises(ValueError):
            pv_sys_mngr.run(name="EastWest", fc_type="wrong_fc_type", weather_df=weather_df)
