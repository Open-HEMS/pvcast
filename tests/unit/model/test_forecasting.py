"""Unit tests for PV power/energy forecasting logic."""
from __future__ import annotations

import datetime as dt
import secrets
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urljoin

import polars as pl
import pytest
import responses

from pvcast.model.const import PVGIS_TMY_END, PVGIS_TMY_START, VALID_UPSAMPLE_FREQ
from pvcast.model.forecasting import (
    ForecastResult,
    ForecastType,
    PowerEstimate,
)

if TYPE_CHECKING:
    from pvcast.model.model import PVPlantModel

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

# temporary location only
PVGIS_TEMP_LOC = Path("tests/data/pvgis_temp")

# actual PVGIS data
PVGIS_RAW_DATA = Path("tests/data/pvgis_out.txt")
PVGIS_PROC_CSV = Path("tests/data/pvgis_out.csv")

EU_JRC_URL = "https://re.jrc.ec.europa.eu/api/tmy"


class TestForecastResult:
    """Test the ForecastResult class."""

    @pytest.fixture(scope="session")
    def pvgis_test_data(self) -> str:
        """Load the PVGIS test data from a text file."""
        with Path.open(PVGIS_RAW_DATA) as data_file:
            return data_file.read()

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
        return ac_series.with_columns(
            pl.col("datetime").str.to_datetime("%Y-%m-%dT%H:%M:%S%z")
        )

        # convert column names

    @pytest.fixture
    def forecast_result(self, forecast_df: pl.DataFrame) -> ForecastResult:
        """Return a ForecastResult instance."""
        return ForecastResult(
            name="test",
            fc_type=ForecastType.CLEARSKY,
            ac_power=forecast_df,
        )

    @pytest.mark.parametrize(
        ("ac_power", "expected_exception", "match"),
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
    def test_init_exceptions(
        self, ac_power: pl.DataFrame, expected_exception: type[Exception], match: str
    ) -> None:
        """Test various exceptions during forecast result initialization."""
        with pytest.raises(expected_exception, match=match):
            ForecastResult(
                name="test", fc_type=ForecastType.CLEARSKY, ac_power=ac_power
            )

    @pytest.mark.parametrize(
        ("frequency", "expected"),
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

    def test_frequency_ac_power_missing(self, forecast_result: ForecastResult) -> None:
        """Test that forecast result frequency returns -1 with no AC power data."""
        forecast_result.ac_power = None
        assert forecast_result.frequency == -1

    def test_frequency_unsorted_datetimes(
        self, forecast_result: ForecastResult
    ) -> None:
        """Test that forecast result frequency returns -1 with unsorted datetimes."""
        forecast_result.ac_power = forecast_result.ac_power.select(
            pl.col("datetime").shuffle(seed=42)
        )
        with pytest.raises(ValueError, match="Datetime column must be sorted"):
            _ = forecast_result.frequency

    def test_frequency_missing_datetimes(self, forecast_result: ForecastResult) -> None:
        """Test that forecast result frequency returns -1 with missing datetimes."""
        forecast_result.ac_power = forecast_result.ac_power.with_row_index(
            "row_nr"
        ).filter(pl.col("row_nr") != 1)
        with pytest.raises(
            ValueError, match="Datetime column must be equidistantly spaced in time."
        ):
            _ = forecast_result.frequency

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
        fc_energy = forecast_result.energy(period).sum()
        assert isinstance(fc_energy, pl.DataFrame)
        ac_energy: pl.Series = fc_energy["ac_energy"]
        assert ac_energy.item() == pytest.approx(
            sum_power["ac_energy"].item(), rel=0.05
        )

    def test_energy_ac_power_unavailable(self, forecast_result: ForecastResult) -> None:
        """Test that forecast result energy calculation fails with no AC power data."""
        forecast_result.ac_power = None
        with pytest.raises(
            ValueError,
            match="AC power output is not available, cannot calculate energy. Run simulation first.",
        ):
            forecast_result.energy("1h")

    def test_energy_invalid_period(self, forecast_result: ForecastResult) -> None:
        """Test that forecast result energy calculation fails with invalid period."""
        with pytest.raises(
            ValueError,
            match=r"Invalid frequency suffix. Must be one of \('h', 'd', 'w', 'mo', 'y'\)\.",
        ):
            forecast_result.energy("1x")

    def test_energy_invalid_ac_power_frequency(
        self, forecast_result: ForecastResult
    ) -> None:
        """Test that forecast result energy calculation fails with invalid AC power frequency."""
        assert forecast_result.ac_power is not None
        forecast_result.ac_power = forecast_result.ac_power.with_row_index(
            "row_nr"
        ).filter(pl.col("row_nr") % 2 == 0)
        with pytest.raises(
            ValueError,
            match="Cannot calculate energy for data with frequency 7200s. Must be <= 1H.",
        ):
            forecast_result.energy("1h")

    @pytest.mark.parametrize(
        ("time_str", "expected"),
        [
            ("10s", 10),
            ("10m", 600),
            ("10h", 36000),
            ("10d", 864000),
            ("10x", ValueError),
        ],
    )
    def testtime_str_to_seconds(
        self,
        forecast_result: ForecastResult,
        time_str: str,
        expected: int | type[Exception],
    ) -> None:
        """Test that forecast result time_str_to_seconds method works."""
        if isinstance(expected, type) and issubclass(expected, Exception):
            with pytest.raises(expected):
                forecast_result.time_str_to_seconds(time_str)
        else:
            assert forecast_result.time_str_to_seconds(time_str) == expected

    @pytest.mark.parametrize("drop", [None, "temperature", "humidity"])
    def test_add_precipitable_water(
        self, pv_plant_model: PVPlantModel, weather_df: pl.DataFrame, drop: str | None
    ) -> None:
        """Test the add_precipitable_water method with missing data."""
        if drop is not None:
            weather_df = weather_df.drop(drop)
            with pytest.raises(
                ValueError, match=f"Missing columns: { {drop} } in weather_df."
            ):
                _ = pv_plant_model.live.run(weather_df)
        else:
            result: ForecastResult = pv_plant_model.live.run(weather_df)
            assert result.fc_type == ForecastType.LIVE
            assert result.ac_power is not None
            assert "ac_power" in result.ac_power.columns
            assert result.ac_power["ac_power"].dtype == pl.Int64

    def test_add_precipitable_water_already_present(
        self, pv_plant_model: PVPlantModel, weather_df: pl.DataFrame
    ) -> None:
        """Test the add_precipitable_water method."""
        weather_df = weather_df.with_columns(pl.lit(1).alias("precipitable_water"))
        result: ForecastResult = pv_plant_model.live.run(weather_df)
        assert result.fc_type == ForecastType.LIVE
        assert result.ac_power is not None
        assert "ac_power" in result.ac_power.columns
        assert result.ac_power["ac_power"].dtype == pl.Int64

    @pytest.mark.parametrize(
        "fc_type",
        [
            pytest.param(ForecastType.HISTORICAL, marks=pytest.mark.integration),
            pytest.param(ForecastType.CLEARSKY),
            pytest.param(ForecastType.LIVE),
        ],
    )
    def test_power_run(
        self,
        pv_plant_model: PVPlantModel,
        weather_df: pl.DataFrame,
        fc_type: ForecastType,
    ) -> None:
        """Test the power estimate run method."""
        estimator: PowerEstimate = getattr(pv_plant_model, fc_type.value)
        result: ForecastResult = estimator.run(weather_df)
        assert isinstance(result, ForecastResult)
        assert result.name == "EastWest"
        assert result.fc_type == fc_type
        assert result.ac_power is not None
        assert "ac_power" in result.ac_power.columns
        assert result.ac_power["ac_power"].dtype == pl.Int64

    @pytest.mark.parametrize(
        "fc_type",
        [
            pytest.param(ForecastType.CLEARSKY),
            pytest.param(ForecastType.LIVE),
        ],
    )
    def test_power_run_weather_df_none(
        self,
        pv_plant_model: PVPlantModel,
        fc_type: ForecastType,
    ) -> None:
        """Test the power estimate run method with no weather data."""
        estimator: PowerEstimate = getattr(pv_plant_model, fc_type.value)
        with pytest.raises(ValueError, match="Must provide weather data."):
            _ = estimator.run(None)

    @pytest.mark.parametrize("use_weather_df", [True, False])
    def test_power_run_historical_data_present(
        self,
        pv_plant_model: PVPlantModel,
        weather_df: pl.DataFrame,
        *,
        use_weather_df: bool,
    ) -> None:
        """Test the power estimate run method for historical data already present."""
        pv_plant_model.historical._pvgis_data_path = Path(PVGIS_PROC_CSV)
        if use_weather_df:
            result: ForecastResult = pv_plant_model.historical.run(weather_df)
        else:
            result: ForecastResult = pv_plant_model.historical.run(None)
        assert isinstance(result, ForecastResult)
        assert result.name == "EastWest"
        assert result.fc_type == ForecastType.HISTORICAL
        assert result.ac_power is not None
        assert "ac_power" in result.ac_power.columns
        assert result.ac_power["ac_power"].dtype == pl.Int64

    def test_power_run_historical_data_missing(
        self,
        pv_plant_model: PVPlantModel,
        pvgis_test_data: str,
    ) -> None:
        """Test the power estimate run method when data has to be requested from PVGIS."""
        lat = str(round(pv_plant_model.location.latitude, 4))
        lon = str(round(pv_plant_model.location.longitude, 4))
        pv_plant_model.historical._pvgis_data_path = Path(
            f"{PVGIS_TEMP_LOC}_{secrets.randbelow(100000)}.csv"
        )

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                urljoin(
                    EU_JRC_URL,
                    f"?lat={lat}&lon={lon}&outputformat=json&startyear={PVGIS_TMY_START}&endyear={PVGIS_TMY_END}",
                ),
                body=pvgis_test_data,
                status=200,
            )
            result: ForecastResult = pv_plant_model.historical.run(None)
            assert isinstance(result, ForecastResult)
            assert result.name == "EastWest"
            assert result.fc_type == ForecastType.HISTORICAL
            assert result.ac_power is not None
            assert "ac_power" in result.ac_power.columns
            assert result.ac_power["ac_power"].dtype == pl.Int64

        # test that the data is saved to the correct location
        assert pv_plant_model.historical._pvgis_data_path.exists()
        assert pv_plant_model.historical._pvgis_data_path.is_file()

        # clean up data file
        pv_plant_model.historical._pvgis_data_path.unlink()
        assert not pv_plant_model.historical._pvgis_data_path.exists()
