"""Contains the FastAPI router for the /live endpoint."""
from __future__ import annotations

import datetime as dt  # noqa: TCH003
import logging
from typing import Any

import polars as pl
from fastapi import APIRouter, Depends, Query
from typing_extensions import Annotated

from pvcast.model.model import PVSystemManager  # noqa: TCH001
from pvcast.weather.weather import WeatherAPI  # noqa: TCH001
from pvcast.webserver.models.base import (
    Interval,
    PVPlantNames,
)
from pvcast.webserver.models.live import LiveModel, WeatherSources
from pvcast.webserver.routers.dependencies import (
    get_pv_system_mngr,  # noqa: TCH001
    get_weather_sources,  # noqa: TCH001
)

from .helpers import get_forecast_result_dict

router = APIRouter()

_LOGGER = logging.getLogger("uvicorn")


@router.get("/{plant_name}/{interval}/{weather_source}")
def get(  # pylint: disable=too-many-arguments
    plant_name: PVPlantNames,
    weather_source: WeatherSources,
    pv_system_mngr: Annotated[PVSystemManager, Depends(get_pv_system_mngr)],
    weather_apis: Annotated[tuple[WeatherAPI], Depends(get_weather_sources)],
    start: Annotated[
        dt.datetime | None,
        Query(
            description="Start datetime in ISO format. Leave empty for no filter. Must be UTC."
        ),
    ] = None,
    end: Annotated[
        dt.datetime | None,
        Query(
            description="End datetime in ISO format. Leave empty for no filter. Must be UTC."
        ),
    ] = None,
    interval: Interval = Interval.H1,
) -> LiveModel:
    """Get the estimated PV output power in Watts.

    Forecast is provided at interval <interval> for the given PV system <name>.

    NB: Power data is defined to represent the state at the beginning of the interval \
    and what is going to happenin this interval.

    :param plant_name: Name of the PV system
    :param interval: Interval of the returned data
    :return: Estimated PV power output in Watts at the given interval <interval> for the given PV system <name>
    """
    # get the correct weather API from the list of weather APIs
    weather_apis_f = filter(lambda api: api.name == weather_source.value, weather_apis)
    weather_api: WeatherAPI = next(weather_apis_f)

    # convert dict to dataframe
    weather_dict: dict[str, Any] = weather_api.get_weather(calc_irrads=True)
    weather_df = pl.DataFrame(weather_dict["data"]).with_columns(
        pl.col("datetime").str.to_datetime()
    )

    # filter weather data between start and end timestamps
    if start is not None:
        weather_df = weather_df.filter(weather_df["datetime"] >= start)
    if end is not None:
        weather_df = weather_df.filter(weather_df["datetime"] < end)

    # get the PV power output
    response_dict = get_forecast_result_dict(
        str(plant_name.name), pv_system_mngr, "live", interval, weather_df
    )

    # add weather source from weather_dict to response_dict
    response_dict["weather_source"] = weather_dict["source"]
    return LiveModel(**response_dict)
