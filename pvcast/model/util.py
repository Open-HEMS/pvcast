"""Utility functions for the pvcast model."""
from datetime import timedelta
from typing import Union

from .const import (
    SECONDS_PER_DAY,
)


def _timedelta_to_pl_duration(td: Union[timedelta, str, None]) -> Union[str, None]:
    """Convert python timedelta to a polars duration string.
    This function is copied from polars' utils.py.
    """
    if td is None or isinstance(td, str):
        return td

    if td.days >= 0:
        d = td.days and f"{td.days}d" or ""
        s = td.seconds and f"{td.seconds}s" or ""
        us = td.microseconds and f"{td.microseconds}us" or ""
    else:
        if not td.seconds and not td.microseconds:
            d = td.days and f"{td.days}d" or ""
            s = ""
            us = ""
        else:
            corrected_d = td.days + 1
            d = corrected_d and f"{corrected_d}d" or "-"
            corrected_seconds = SECONDS_PER_DAY - (td.seconds + (td.microseconds > 0))
            s = corrected_seconds and f"{corrected_seconds}s" or ""
            us = td.microseconds and f"{10**6 - td.microseconds}us" or ""

    return f"{d}{s}{us}"
