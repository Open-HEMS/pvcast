"""Webserver data models base module."""
from __future__ import annotations

import datetime
from enum import Enum

from pydantic import BaseModel, validator
from typing_extensions import Annotated

from ..routers.dependencies import get_pv_system_mngr

data_example = {
    "plant_name": "My PV System",
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


class PowerInterval(str, Enum):
    """Power interval enum."""

    MIN1 = "1Min"
    MIN5 = "5Min"
    MIN15 = "15Min"
    MIN30 = "30Min"
    H1 = "1H"


class EnergyInterval(str, Enum):
    """Energy interval enum."""

    H1 = "1H"
    D1 = "1D"
    W1 = "1W"
    M1 = "1M"
    Y1 = "1Y"


class BaseDataModel(BaseModel):
    """Base data model."""

    plant_name: Annotated[str, "Name of the PV system"]
    start: Annotated[str | None, "Start time of the returned data."]
    end: Annotated[str | None, "End time of the returned data."]
    timezone: Annotated[str | None, "Timezone of the returned data"] = "UTC"
    result: Annotated[dict[str, int], "Result of the returned data"] = data_example["result"]


class BasePowerModel(BaseDataModel):
    """Base power model."""

    unit: Annotated[str, "Electrical unit of the returned data"] = "W"
    interval: Annotated[PowerInterval, "Interval of the returned data"]


class BaseEnergyModel(BaseDataModel):
    """Base energy model."""

    unit: Annotated[str, "Electrical unit of the returned data"] = "Wh"
    interval: Annotated[EnergyInterval, "Interval of the returned data"]


class StartEndRequest(BaseModel):
    """Start end request body model."""

    start: Annotated[datetime.datetime, "Start time of the returned data."] = "2023-09-19T15:39+00:00"
    end: Annotated[datetime.datetime, "End time of the returned data."] = "2023-09-20T15:39+00:00"

    @validator("start", "end", pre=True)
    def parse_datetime(cls, value: str) -> datetime:  # pylint: disable=no-self-argument; # noqa: B902
        """Parse datetime."""
        date_time = datetime.datetime.fromisoformat(value)
        if date_time.tzinfo is None:
            raise ValueError("Timezone must be specified.")
        return date_time.astimezone(datetime.timezone.utc)


# create enum of pv plant names
pv_plant_names = {name: name for name in get_pv_system_mngr().plant_names}
pv_plant_names["All"] = "All"
TypeEnum = Enum("TypeEnum", pv_plant_names)


class TempEnum(str, Enum):
    """Proxy enum."""


PVPlantNames = TempEnum("TypeEnum", pv_plant_names)
