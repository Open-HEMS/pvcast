"""Webserver data models base module."""
from __future__ import annotations

import datetime
from enum import Enum

from pydantic import BaseModel, validator
from typing_extensions import Annotated

from ...model.model import PVSystemManager
from ..routers.dependencies import get_pv_system_mngr

res_examp = {
    "watt": {
        "EastWest": {
            "2023-09-19T15:00:00+0000": 1428,
            "2023-09-19T16:00:00+0000": 1012,
            "2023-09-19T17:00:00+0000": 279,
            "2023-09-19T18:00:00+0000": 0,
        }
    },
    "watt_hours": {
        "EastWest": {
            "2023-09-19T15:00:00+0000": 1428,
            "2023-09-19T16:00:00+0000": 1012,
            "2023-09-19T17:00:00+0000": 279,
            "2023-09-19T18:00:00+0000": 0,
        }
    },
    "watt_hours_cumsum": {
        "EastWest": {
            "2023-09-19T15:00:00+0000": 1428,
            "2023-09-19T16:00:00+0000": 2440,
            "2023-09-19T17:00:00+0000": 2719,
            "2023-09-19T18:00:00+0000": 2719,
        }
    },
}

data_example = {
    "clearskymodel": "Ineichen",
    "start": "2023-09-19T15:00:00+0000",
    "end": "2023-09-20T15:00:00+0000",
    "timezone": "UTC",
    "interval": "1H",
    "result": res_examp,
}


class Interval(str, Enum):
    """Power interval enum."""

    MIN1 = "1Min"
    MIN5 = "5Min"
    MIN15 = "15Min"
    MIN30 = "30Min"
    H1 = "1H"


class PowerData(BaseModel):
    """Power data model."""

    watt: dict[str, dict[str, int]]
    watt_hours: dict[str, dict[str, int]]
    watt_hours_cumsum: dict[str, dict[str, int]]


class BaseDataModel(BaseModel):
    """Base data model."""

    start: Annotated[str | None, "Start time of the returned data."]
    end: Annotated[str | None, "End time of the returned data."]
    timezone: Annotated[str | None, "Timezone of the returned data"] = "UTC"
    interval: Annotated[Interval, "Interval of the returned data"]
    result: Annotated[PowerData, "Result of the returned data"] = PowerData(**res_examp)


class StartEndRequest(BaseModel):
    """Start end request body model."""

    start: Annotated[
        datetime.datetime, "Start time of the returned data."
    ] = datetime.datetime.now(datetime.timezone.utc)
    end: Annotated[datetime.datetime, "End time of the returned data."] = (
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)
    )

    @validator("start", "end", pre=True)
    def parse_datetime(cls, value: str) -> datetime.datetime:  # pylint: disable=no-self-argument; # noqa: B902
        """Parse datetime."""
        date_time = datetime.datetime.fromisoformat(value)
        if date_time.tzinfo is None:
            raise ValueError("Timezone must be specified.")
        dt_in_tz = date_time.astimezone(datetime.timezone.utc)
        return dt_in_tz


# create enum of pv plant names
sys_mngr: PVSystemManager = get_pv_system_mngr()
pv_plant_names = {str(name): str(name) for name in sys_mngr.plant_names}
pv_plant_names["All"] = "All"
TypeEnum = Enum("TypeEnum", pv_plant_names)  # type: ignore[misc]


class TempEnum(str, Enum):
    """Proxy enum."""


PVPlantNames = TempEnum("TypeEnum", pv_plant_names)  # type: ignore[call-overload]
