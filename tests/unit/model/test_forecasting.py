"""Unit tests for PV power/energy forecasting logic."""
from __future__ import annotations

from datetime import timedelta
from typing import Type, Union

import polars as pl
import pytest

from pvcast.model.const import VALID_UPSAMPLE_FREQ
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
    def forecast_df(self) -> pl.DataFrame:
        """Return a DataFrame with test data."""
        # re-orient the test_ac_power dict to {time: [timestamps], ac_power: [values]}
        ac_data = {
            "time": list(test_ac_power.keys()),
            "ac_power": list(test_ac_power.values()),
        }

        # create a polars series from the test dict
        ac_series = pl.from_dict(ac_data, schema={"time": str, "ac_power": pl.Int64})

        # convert timestamps to datetime
        ac_series = ac_series.with_columns(
            pl.col("time").str.to_datetime("%Y-%m-%dT%H:%M:%S%z")
        )

        # convert column names
        return ac_series

    @pytest.fixture
    def forecast_result(self, forecast_df: pl.DataFrame) -> ForecastResult:
        """Return a ForecastResult instance."""

        # convert column names
        return ForecastResult(
            name="test",
            type=ForecastType.CLEARSKY,
            ac_power=forecast_df,
        )

    def test_init_no_timestamps(self) -> None:
        """Test that forecast result init fails with no timestamps."""
        with pytest.raises(ValueError, match="AC power data must have a 'time'"):
            ForecastResult(
                name="test",
                type=ForecastType.CLEARSKY,
                ac_power=pl.from_dict({"ac_power": [1, 2, 3]}),
            )

    def test_init_null_data(self, forecast_df: pl.DataFrame) -> None:
        """Test that forecast result init fails with null data."""
        forecast_df[0, "ac_power"] = None
        print(forecast_df)
        with pytest.raises(ValueError, match="AC power data contains null values."):
            ForecastResult(
                name="test",
                type=ForecastType.CLEARSKY,
                ac_power=forecast_df,
            )

    def test_init_ac_power_col_missing(self, forecast_df: pl.DataFrame) -> None:
        """Test that forecast result init fails with missing ac_power column."""
        forecast_df = forecast_df.drop("ac_power")
        with pytest.raises(
            ValueError, match="AC power data must have a 'ac_power' column."
        ):
            ForecastResult(
                name="test",
                type=ForecastType.CLEARSKY,
                ac_power=forecast_df,
            )

    @pytest.mark.parametrize(
        "frequency, expected",
        [
            ("1h", 3600),
            ("60m", 3600),
            ("30m", 1800),
            ("15m", 900),
            ("5m", 300),
            ("1m", 60),
        ],
    )
    def test_upsample(
        self, forecast_result: ForecastResult, frequency: str, expected: int
    ) -> None:
        """Test that forecast result upsampling works."""
        assert frequency in VALID_UPSAMPLE_FREQ
        assert forecast_result.frequency == 3600
        fc_ups: ForecastResult = forecast_result.upsample(frequency)
        assert fc_ups.frequency == expected

    def test_upsample_invalid_frequency(self, forecast_result: ForecastResult) -> None:
        """Test that forecast result upsampling fails with invalid frequency."""
        with pytest.raises(ValueError, match="Invalid frequency"):
            forecast_result.upsample("99s")
        with pytest.raises(ValueError, match="Invalid frequency"):
            forecast_result.upsample(99)

    def test_upsample_too_low_frequency(self, forecast_result: ForecastResult) -> None:
        """Test that forecast result upsampling fails with too low frequency."""
        forecast_result = forecast_result.upsample("30m")
        with pytest.raises(ValueError, match="Cannot upsample to a lower frequency"):
            forecast_result.upsample("1h")

    def test_upsample_ac_power_none(self, forecast_result: ForecastResult) -> None:
        """Test that forecast result upsampling fails with no AC power data."""
        forecast_result.ac_power = None
        with pytest.raises(ValueError, match="No AC power data"):
            forecast_result.upsample("1h")

    @pytest.mark.parametrize("period", ["1h", "1d", "1w", "1mo", "1y"])
    @pytest.mark.parametrize("freq", ["1h", "60m", "30m", "15m", "5m", "1m"])
    def test_energy(
        self, forecast_result: ForecastResult, period: str, freq: str
    ) -> None:
        """Test that forecast result energy calculation works."""
        sum_power = forecast_result.ac_power.sum().rename({"ac_power": "ac_energy"})

        # upsample to the desired frequency
        forecast_result = forecast_result.upsample(freq)

        # power data is hourly, so the sum == energy
        fc_energy: ForecastResult = forecast_result.energy(period).sum()
        ac_energy: pl.Series = fc_energy["ac_energy"]
        assert ac_energy.item() == pytest.approx(
            sum_power["ac_energy"].item(), rel=0.05
        )

    @pytest.mark.parametrize(
        ("td", "expected"),
        [
            (timedelta(days=1), "1d"),
            (timedelta(days=-1), "-1d"),
            (timedelta(seconds=1), "1s"),
            (timedelta(seconds=-1), "-1s"),
            (timedelta(microseconds=1), "1us"),
            (timedelta(microseconds=-1), "-1us"),
            (timedelta(days=1, seconds=1), "1d1s"),
            (timedelta(days=-1, seconds=-1), "-1d1s"),
            (timedelta(days=1, microseconds=1), "1d1us"),
            (timedelta(days=-1, microseconds=-1), "-1d1us"),
        ],
    )
    def test_timedelta_to_pl_duration(
        self, forecast_result: ForecastResult, td: timedelta, expected: str
    ) -> None:
        out = forecast_result._timedelta_to_pl_duration(td)
        assert out == expected

    @pytest.mark.parametrize(
        "time_str, expected",
        [
            ("10s", 10),
            ("10m", 600),
            ("10h", 36000),
            ("10d", 864000),
            ("10x", ValueError),
        ],
    )
    def test_time_str_to_seconds(
        self,
        forecast_result: ForecastResult,
        time_str: str,
        expected: Union[int, Type[Exception]],
    ) -> None:
        if isinstance(expected, type) and issubclass(expected, Exception):
            with pytest.raises(expected):
                forecast_result._time_str_to_seconds(time_str)
        else:
            assert forecast_result._time_str_to_seconds(time_str) == expected
