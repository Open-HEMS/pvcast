"""Test unit conversion utilities."""
from __future__ import annotations

import polars as pl
import pytest
from polars.testing import assert_series_equal

from pvcast.util.units import convert_unit


class TestUnitConversion:
    """Test timestamp utilities."""

    # define valid test cases for speed conversion
    # fmt: off
    valid_speed_test_cases = [
        ("m/s", "km/h", pl.Series([-36.0, 0.0, 90.0, 360.0, 133.2], dtype=pl.Float64)),
        ("km/h", "m/s", pl.Series([-2.78, 0.0, 6.94, 27.78, 10.28], dtype=pl.Float64)),
        ("mi/h", "m/s", pl.Series([-4.47, 0.0, 11.18, 44.70, 16.54], dtype=pl.Float64)),
    ]
    # fmt: on

    # define invalid test cases for speed conversion
    invalid_speed_test_cases = [
        ("m/s", "invalid_unit"),
        ("invalid_unit", "km/h"),
        ("invalid_unit", "invalid_unit"),
        ("invalid_unit", "mi/h"),
    ]

    # Define test data
    unit_conv_data = pl.Series(
        "temperature",
        [-10.0, 0.0, 25.0, 100.0, 37.0],
        dtype=pl.Float64,
    )

    # fahrenheit to celsius conversion
    f_to_c_out = pl.Series(
        "temperature",
        [-23.3333, -17.7778, -3.8889, 37.7778, 2.7778],
        dtype=pl.Float64,
    )

    # define valid test cases for temperature conversion
    # fmt: off
    valid_temperature_test_cases = [
        ("°F", "°C", f_to_c_out),
        ("°F", "C", f_to_c_out),
        ("F", "°C", f_to_c_out),
        ("F", "C", f_to_c_out),
        ("C", "C", unit_conv_data),
    ]
    # fmt: on

    # define invalid test cases for temperature conversion
    invalid_temperature_test_cases = [
        ("C", "invalid_unit"),
        ("invalid_unit", "C"),
        ("invalid_unit", "invalid_unit"),
        ("invalid_unit", "F"),
    ]

    @pytest.mark.parametrize(
        "from_unit, to_unit, expected",
        valid_temperature_test_cases + valid_speed_test_cases,
    )
    def test_valid_conversion(
        self,
        from_unit: str,
        to_unit: str,
        expected: pl.Series,
    ) -> None:
        result = convert_unit(self.unit_conv_data, from_unit, to_unit)
        assert isinstance(result, pl.Series)
        assert_series_equal(
            result,
            expected,
            check_dtype=False,
            atol=0.01,
            check_exact=False,
            check_names=False,
        )

    @pytest.mark.parametrize(
        "from_unit, to_unit", invalid_temperature_test_cases + invalid_speed_test_cases
    )
    def test_invalid_conversion(self, from_unit: str, to_unit: str) -> None:
        with pytest.raises(ValueError):
            convert_unit(self.unit_conv_data, from_unit, to_unit)

    def test_invalid_data_type(self) -> None:
        with pytest.raises(TypeError):
            convert_unit([0, 25, 100, 37], "C", "F")
