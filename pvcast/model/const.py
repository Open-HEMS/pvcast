"""Constants used throughout the model."""
from __future__ import annotations

from pathlib import Path

BASE_DIR = Path("pvcast")
BASE_CEC_DATA_PATH = BASE_DIR / "data/proc"

VALID_FREQS = ("A", "M", "1W", "1D", "1H", "30Min", "15Min", "5Min", "1Min")

# PVGIS TMY (typical meteorological year) data uses a typical month of a typical year.
# Thus one 'year' of data can consist of dates such as: [Jan 2015, Feb 2008, Mar 2013, ...]
# This is very inconvenient for our purposes, so we will mapp all of it to a single year of data instead.
HISTORICAL_YEAR_MAPPING = 2021
