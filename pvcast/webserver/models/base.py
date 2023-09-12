"""Webserver data models base module."""
from __future__ import annotations

from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel
from typing_extensions import Annotated

data_example = {
    "plantname": "My PV System",
    "interval": "15Min",
    "start": "2023-01-01T00:00:00+00:00",
    "end": "2023-01-01T00:03:00+00:00",
    "timezone": "UTC",
    "result": {
        "2023-01-01T00:00:00+00:00": 0,
        "2023-01-01T00:01:00+00:00": 100,
        "2023-01-01T00:02:00+00:00": 200,
        "2023-01-01T00:03:00+00:00": 300,
    },
}


class Interval(str, Enum):
    """Interval enum."""

    _1MIN = "1Min"
    _5MIN = "5Min"
    _15MIN = "15Min"
    _30MIN = "30Min"
    _1H = "1H"
    _1D = "1D"
    _1W = "1W"
    _1M = "1M"
    _1Y = "1Y"


class BaseDataModel(BaseModel):
    """Base data model."""

    plantname: Annotated[str, "Name of the PV system"]
    interval: Annotated[Interval, "Interval of the returned data"]
    start: Annotated[str | None, "Start time of the returned data."]
    end: Annotated[str | None, "End time of the returned data."]
    timezone: Annotated[str | None, "Timezone of the returned data"] = "UTC"
    result: Annotated[dict[str, int], "Result of the returned data"] = data_example["result"]


class BasePowerModel(BaseDataModel):
    """Base power model."""

    unit: Annotated[str, "Electrical unit of the returned data"] = "W"


class BaseEnergyModel(BaseDataModel):
    """Base energy model."""

    unit: Annotated[str, "Electrical unit of the returned data"] = "Wh"
