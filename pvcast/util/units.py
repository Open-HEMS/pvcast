"""Unit conversion functions."""
from __future__ import annotations

from typing import Callable

import polars as pl

# Define a type for the conversion functions
ConversionFunc = Callable[[pl.Series], pl.Series]

# temperature conversion functions ("°C", "°F", "C", "F")
TEMP_CONV_DICT = {
    "F": {
        "C": lambda x: (5 / 9) * (x - 32),
    },
    "C": {
        "C": lambda x: x,
    },
}

# speed conversion functions ("m/s", "km/h", "mi/h", "ft/s", "kn")
SPEED_CONV_DICT = {
    "m/s": {
        "km/h": lambda x: x * 3.6,
    },
    "km/h": {
        "m/s": lambda x: x / 3.6,
    },
    "mi/h": {
        "m/s": lambda x: x / 2.23694,
    },
    "ft/s": {
        "m/s": lambda x: x / 3.28084,
    },
    "kn": {
        "m/s": lambda x: x / 1.94384,
    },
}

# combine temperature and speed conversion dictionaries
CONV_DICT: dict[str, dict[str, ConversionFunc]] = {**TEMP_CONV_DICT, **SPEED_CONV_DICT}


def convert_unit(data: pl.Series, from_unit: str, to_unit: str) -> pl.Series:
    """Convert units of a pl.Series.

    :param data: The data to convert. This should be a pl.Series.
    :param to_unit: The unit to convert to.
    :return: Data with applied unit conversion.
    """
    if not isinstance(data, pl.Series):
        msg = "Data must be a pl.Series."
        raise TypeError(msg)

    # remove degree symbol from units if present
    from_unit = from_unit.replace("°", "")
    to_unit = to_unit.replace("°", "")

    if from_unit not in CONV_DICT or to_unit not in CONV_DICT[from_unit]:
        msg = f"Conversion from [{from_unit}] to [{to_unit}] not supported."
        raise ValueError(msg)
    if from_unit == to_unit:
        return data

    # do unit conversion
    return CONV_DICT[from_unit][to_unit](data)
