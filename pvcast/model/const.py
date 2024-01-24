"""Constants used throughout the model."""
from __future__ import annotations

from pathlib import Path

CWD = Path(__file__).parent.parent.absolute()
BASE_CEC_DATA_PATH = CWD / "data/proc"

VALID_UPSAMPLE_FREQ = ("1h", "60m", "30m", "15m", "5m", "1m")
VALID_DOWN_SAMPLE_FREQ = ("h", "d", "w", "mo", "y")

SECONDS_PER_HOUR = 3_600

# PVGIS TMY (typical meteorological year) data uses a typical month of a typical year.
# Thus one 'year' of data can consist of dates such as: [Jan 2015, Feb 2008, Mar 2013, ...]
# This is very inconvenient for our purposes, so we will map all of it to a single year of data instead.
HISTORICAL_YEAR_MAPPING = 2021
PVGIS_TMY_START = 2005
PVGIS_TMY_END = 2015

# model attribute constants
CLEARSKY_MODEL_ATTRS: dict[str, str] = {
    "aoi_model": "physical",
    "spectral_model": "no_loss",
}
LIVE_MODEL_ATTRS: dict[str, str] = {}
HISTORICAL_MODEL_ATTRS: dict[str, str] = {}
