"""Webserver data models base module."""
from __future__ import annotations

import datetime
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, validator
from typing_extensions import Annotated

from pvcast.webserver.routers.dependencies import get_pv_system_mngr

if TYPE_CHECKING:
    from pvcast.model.model import PVSystemManager

res_examp = [
    {
        "datetime": "2023-09-19T15:00:00+0000",
        "watt": 1428,
        "watt_cumsum": 1428,
    },
    {
        "datetime": "2023-09-19T15:30:00+0000",
        "watt": 1012,
        "watt_cumsum": 2440,
    },
    {
        "datetime": "2023-09-19T16:00:00+0000",
        "watt": 279,
        "watt_cumsum": 2719,
    },
    {
        "datetime": "2023-09-19T16:30:00+0000",
        "watt": 0,
        "watt_cumsum": 2719,
    },
]


data_example = {
    "clearskymodel": "Ineichen",
    "start": "2023-09-19T15:00:00+0000",
    "end": "2023-09-20T15:00:00+0000",
    "timezone": "UTC",
    "interval": "1h",
    "period": res_examp,
}


class Interval(str, Enum):
    """Power interval enum."""

    MIN1 = "1m"
    MIN5 = "5m"
    MIN15 = "15m"
    MIN30 = "30m"
    H1 = "1h"


class PowerData(BaseModel):
    """Power data model."""

    datetime: str
    watt: int
    watt_cumsum: int


class BaseDataModel(BaseModel):
    """Base data model."""

    start: Annotated[str | None, "Start time of the returned data."]
    end: Annotated[str | None, "End time of the returned data."]
    forecast_type: Annotated[str | None, "Forecast type used to generate the data."]
    plant_name: Annotated[str | None, "Name of the PV system"]
    timezone: Annotated[str | None, "Timezone of the returned data"] = "UTC"
    interval: Annotated[Interval, "Interval of the returned data"]
    period: Annotated[list[PowerData], "PV power at the requested interval."]


class StartEndRequest(BaseModel):
    """Start end request body model."""

    start: Annotated[
        datetime.datetime, "Start time of the returned data."
    ] = datetime.datetime.now(datetime.timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end: Annotated[datetime.datetime, "End time of the returned data."] = (
        datetime.datetime.now(datetime.timezone.utc)
    ).replace(hour=23, minute=59, second=0, microsecond=0)

    @validator("start", "end", pre=True)
    def parse_datetime(cls, value: str) -> datetime.datetime:  # pylint: disable=no-self-argument;
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
