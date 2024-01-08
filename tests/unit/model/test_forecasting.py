"""Unit tests for PV power/energy forecasting logic."""
from __future__ import annotations

import datetime as dt
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
            "datetime": list(test_ac_power.keys()),
            "ac_power": list(test_ac_power.values()),
        }

        # create a polars series from the test dict
        ac_series = pl.from_dict(
            ac_data, schema={"datetime": str, "ac_power": pl.Int64}
        )

        # convert timestamps to datetime
        ac_series = ac_series.with_columns(
            pl.col("datetime").str.to_datetime("%Y-%m-%dT%H:%M:%S%z")
        )

        # convert column names
        return ac_series

    @pytest.fixture
    def forecast_result(self, forecast_df: pl.DataFrame) -> ForecastResult:
        """Return a ForecastResult instance."""
        return ForecastResult(
            name="test",
            type=ForecastType.CLEARSKY,
            ac_power=forecast_df,
        )

    @pytest.mark.parametrize(
        "ac_power, expected_exception, match",
        [
            (None, ValueError, "Must provide AC power data."),
            (
                pl.DataFrame(
                    {"datetime": ["2022-01-01T00:00:00+00:00"], "ac_power": [1]}
                ),
                ValueError,
                "Datetime column must have dtype datetime.datetime",
            ),
            (
                pl.DataFrame(
                    {
                        "datetime": [dt.datetime(2022, 1, 1, tzinfo=dt.timezone.utc)],
                        "ac_power": [1.5],
                    }
                ),
                ValueError,
                "AC power column must have dtype int64",
            ),
            (
                pl.DataFrame({"ac_power": [1, 2, 3]}),
                ValueError,
                "AC power data must have a 'datetime' column",
            ),
            (
                pl.DataFrame(
                    {
                        "datetime": [dt.datetime(2022, 1, 1, tzinfo=dt.timezone.utc)],
                        "ac_power": [None],
                    }
                ),
                ValueError,
                "AC power data contains null values",
            ),
            (
                pl.DataFrame(
                    {"datetime": [dt.datetime(2022, 1, 1, tzinfo=dt.timezone.utc)]}
                ),
                ValueError,
                "AC power data must have a 'ac_power' column",
            ),
        ],
    )
    def test_init_exceptions(self, ac_power, expected_exception, match) -> None:
        """Test various exceptions during forecast result initialization."""
        with pytest.raises(expected_exception, match=match):
            ForecastResult(name="test", type=ForecastType.CLEARSKY, ac_power=ac_power)

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


class TestPowerEstimate:
    # def test_percepitable_water(self, forecast_result: ForecastResult) -> None:
    #     """Test that forecast result percepitable water calculation works."""
    #     assert forecast_result.percepitable_water is None
    pass
