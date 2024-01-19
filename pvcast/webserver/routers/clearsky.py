"""FastAPI router for the /clearsky endpoint."""
from __future__ import annotations

import datetime as dt

import polars as pl
from fastapi import APIRouter, Depends, Query
from typing_extensions import Annotated

from pvcast.model.model import PVSystemManager  # noqa: TCH001
from pvcast.weather.weather import WeatherAPI  # noqa: TCH001
from pvcast.webserver.const import END_DT_DEFAULT, START_DT_DEFAULT
from pvcast.webserver.models.base import (
    Interval,
    PVPlantNames,
)
from pvcast.webserver.models.clearsky import ClearskyModel
from pvcast.webserver.routers.dependencies import (
    get_pv_system_mngr,  # noqa: TCH001
    get_weather_sources,  # noqa: TCH001
)

from .helpers import get_forecast_result_dict

router = APIRouter()


@router.get("/{plant_name}/{interval}")
def get(
    plant_name: PVPlantNames,
    pv_system_mngr: Annotated[PVSystemManager, Depends(get_pv_system_mngr)],
    weather_apis: Annotated[list[WeatherAPI], Depends(get_weather_sources)],
    start: Annotated[
        dt.datetime, Query(description="Start datetime in ISO format.")
    ] = START_DT_DEFAULT,
    end: Annotated[
        dt.datetime, Query(description="End datetime in ISO format.")
    ] = END_DT_DEFAULT,
    interval: Interval = Interval.H1,
) -> ClearskyModel:
    """Get the estimated PV output power in Watts.

    Forecast is provided at interval <interval> for the given PV system <name>.

    NB: Power data is defined to represent the state at the beginning of the interval \
    and what is going to happenin this interval.

    :param plant_name: Name of the PV system
    :param interval: Interval of the returned data
    :return: Estimated PV power output in Watts at the given interval <interval> for the given PV system <name>
    """
    # for clearsky we don't care which weather API is used, so just use the first one
    weather_api = weather_apis[0]

    # build the datetime index
    datetimes = weather_api.get_source_dates(start, end, dt.timedelta(hours=1))
    # convert datetimes to dataframe
    weather_df = pl.DataFrame(datetimes.alias("datetime"))

    # get the PV power output
    response_dict = get_forecast_result_dict(
        str(plant_name.name), pv_system_mngr, "clearsky", interval, weather_df
    )
    return ClearskyModel(**response_dict)
