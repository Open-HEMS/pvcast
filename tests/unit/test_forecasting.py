from __future__ import annotations

from pathlib import Path
from types import MappingProxyType

import pytest
from pvlib.location import Location

from pvcast.model.forecasting import ForecastResult
from pvcast.model.model import PVPlantModel, PVSystemManager


class TestPVModelChain:
    location = (latitude, longitude) = (52.35855344250755, 4.881086336486702)
    altitude = 10.0
