"""Unit tests for PV power/energy forecasting logic."""
from __future__ import annotations

import datetime

import numpy as np
import pandas as pd
import pytest

from pvcast.model.forecasting import ForecastResult, ForecastType

# test dict for AC power output
test_ac_power = {
    "2023-09-19T15:00:00+0000": 1428,
    "2023-09-19T16:00:00+0000": 1012,
    "2023-09-19T17:00:00+0000": 279,
    "2023-09-19T18:00:00+0000": 0,
    "2023-09-19T19:00:00+0000": 0,
    "2023-09-19T20:00:00+0000": 0,
    "2023-09-19T21:00:00+0000": 0,
    "2023-09-19T22:00:00+0000": 0,
    "2023-09-19T23:00:00+0000": 0,
    "2023-09-20T00:00:00+0000": 0,
    "2023-09-20T01:00:00+0000": 0,
    "2023-09-20T02:00:00+0000": 0,
    "2023-09-20T03:00:00+0000": 0,
    "2023-09-20T04:00:00+0000": 0,
    "2023-09-20T05:00:00+0000": 0,
    "2023-09-20T06:00:00+0000": 111,
    "2023-09-20T07:00:00+0000": 541,
    "2023-09-20T08:00:00+0000": 788,
    "2023-09-20T09:00:00+0000": 1022,
    "2023-09-20T10:00:00+0000": 1428,
    "2023-09-20T11:00:00+0000": 1752,
    "2023-09-20T12:00:00+0000": 1906,
    "2023-09-20T13:00:00+0000": 1872,
    "2023-09-20T14:00:00+0000": 1674,
    "2023-09-20T15:00:00+0000": 1412,
    "2023-09-20T16:00:00+0000": 988,
    "2023-09-20T17:00:00+0000": 250,
    "2023-09-20T18:00:00+0000": 0,
    "2023-09-20T19:00:00+0000": 0,
    "2023-09-20T20:00:00+0000": 0,
    "2023-09-20T21:00:00+0000": 0,
    "2023-09-20T22:00:00+0000": 0,
    "2023-09-20T23:00:00+0000": 0,
    "2023-09-21T00:00:00+0000": 0,
    "2023-09-21T01:00:00+0000": 0,
    "2023-09-21T02:00:00+0000": 0,
    "2023-09-21T03:00:00+0000": 0,
    "2023-09-21T04:00:00+0000": 0,
    "2023-09-21T05:00:00+0000": 0,
    "2023-09-21T06:00:00+0000": 100,
    "2023-09-21T07:00:00+0000": 531,
    "2023-09-21T08:00:00+0000": 780,
    "2023-09-21T09:00:00+0000": 1009,
    "2023-09-21T10:00:00+0000": 1412,
    "2023-09-21T11:00:00+0000": 1735,
    "2023-09-21T12:00:00+0000": 1889,
    "2023-09-21T13:00:00+0000": 1854,
    "2023-09-21T14:00:00+0000": 1655,
    "2023-09-21T15:00:00+0000": 1395,
}


class TestForecastResult:
    """Test the ForecastResult class."""

    @pytest.fixture
    def forecast_result(self):
        """Return a ForecastResult instance."""
        datetimes = pd.to_datetime(list(test_ac_power.keys()))
        ac_series = pd.Series(test_ac_power.values(), dtype="int64", index=datetimes)
        return ForecastResult(
            name="test",
            type=ForecastType.CLEARSKY,
            ac_power=ac_series,
            dc_power=None,
        )

    @pytest.fixture
    def forecast_result_year(self, forecast_result):
        """Duplicate the forecast_result to fill a year."""
        ac_power = pd.concat([forecast_result.ac_power] * 200, ignore_index=True)[:8766]

        # build index datetimes for one year
        index_dt = pd.date_range(
            start=forecast_result.ac_power.index[0],
            periods=len(ac_power),
            freq=forecast_result.ac_power.index.freq,
            tz=forecast_result.ac_power.index.tz,
        )

        # build ac_power dataframe with one year of data
        ac_power = pd.Series(ac_power.values, index=index_dt)

        # build ForecastResult instance
        return ForecastResult(
            name="test",
            type=ForecastType.CLEARSKY,
            ac_power=ac_power,
            dc_power=None,
        )

    def test_forecast_creation(self, forecast_result):
        """Test the ForecastResult class."""
        assert forecast_result.name == "test"
        assert forecast_result.type == ForecastType.CLEARSKY
        assert isinstance(forecast_result.ac_power, pd.Series)
        assert forecast_result.ac_power.dtype == "int64"
        assert forecast_result.ac_power.index.freq == "H"
        assert forecast_result.ac_power.index.tzinfo == datetime.timezone.utc
        assert forecast_result.dc_power is None

    def test_forecast_energy_property(self, forecast_result):
        """Test the ForecastResult class."""
        energy = forecast_result.ac_energy
        assert isinstance(energy, pd.Series)
        assert energy.dtype == "int64"
        assert energy.index.freq == "H"
        # hourly energy should be equal to hourly power (1 kWh/h = 1 kW)
        assert (energy.values == forecast_result.ac_power.values).all()

    @pytest.mark.parametrize("freq", ["1H", "30Min", "15Min", "5Min", "1Min"])
    def test_forecast_energy_function(self, forecast_result, freq):
        """Test the energy function for intervals smaller than 1 hour."""
        # resample to 30 min
        forecast_result_res = forecast_result.resample(freq)
        assert forecast_result_res.ac_power.index.freq == freq
        assert forecast_result_res.ac_power.dtype == "int64"
        energy = forecast_result_res.ac_energy
        assert isinstance(energy, pd.Series)
        assert energy.dtype == "int64"
        assert energy.index.freq == freq
        # calculate power -> energy conversion factor
        conv_factor = pd.Timedelta(freq).total_seconds() / 3600
        assert np.allclose(
            energy.values, forecast_result_res.ac_power.values * conv_factor, atol=3
        )

    @pytest.mark.parametrize("freq", ["1D", "1W", "M", "A"])
    def test_forecast_energy_function_sum(self, forecast_result_year, freq):
        """Test the energy function for intervals larger than 1 hour."""
        energy = forecast_result_year.energy(freq)
        assert isinstance(energy, pd.Series)
        assert energy.dtype == "int64"
        assert energy.index.freq == freq
