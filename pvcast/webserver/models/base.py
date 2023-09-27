"""Webserver data models base module."""
from __future__ import annotations

import datetime
from enum import Enum

from pydantic import BaseModel, validator
from typing_extensions import Annotated

from ..routers.dependencies import get_pv_system_mngr

data_example = {
    "interval": "15Min",
    "start": "2023-01-01T00:00:00+00:00",
    "end": "2023-01-01T00:03:00+00:00",
    "timezone": "UTC",
    "result": {
        "EastWest": {
            "watts": {
                "2023-01-01T00:00:00+00:00": 0,
                "2023-01-01T00:01:00+00:00": 100,
                "2023-01-01T00:02:00+00:00": 200,
                "2023-01-01T00:03:00+00:00": 300,
            },
            "watt_hours": {
                "2023-01-01T00:00:00+00:00": 0,
                "2023-01-01T00:01:00+00:00": 25,
                "2023-01-01T00:02:00+00:00": 50,
                "2023-01-01T00:03:00+00:00": 75,
            },
        },
        "NorthSouth": {
            "watts": {
                "2023-01-01T00:00:00+00:00": 0,
                "2023-01-01T00:01:00+00:00": 100,
                "2023-01-01T00:02:00+00:00": 200,
                "2023-01-01T00:03:00+00:00": 300,
            },
            "watt_hours": {
                "2023-01-01T00:00:00+00:00": 0,
                "2023-01-01T00:01:00+00:00": 25,
                "2023-01-01T00:02:00+00:00": 50,
                "2023-01-01T00:03:00+00:00": 75,
            },
        },
    },
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

    watts: dict[str, int]
    watt_hours: dict[str, int]


class BaseDataModel(BaseModel):
    """Base data model."""

    start: Annotated[str | None, "Start time of the returned data."]
    end: Annotated[str | None, "End time of the returned data."]
    timezone: Annotated[str | None, "Timezone of the returned data"] = "UTC"
    interval: Annotated[Interval, "Interval of the returned data"]
    result: Annotated[dict[str, PowerData], "Result of the returned data"] = data_example["result"]


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
