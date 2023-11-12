"""This module contains the FastAPI router for the /clearsky endpoint."""
from __future__ import annotations

import logging

import pandas as pd
from fastapi import APIRouter, Depends
from typing_extensions import Annotated

from ...model.model import PVSystemManager
from ...weather.weather import WeatherAPI
from ..models.base import Interval, PVPlantNames, StartEndRequest
from ..models.clearsky import ClearskyModel
from ..routers.dependencies import get_pv_system_mngr, get_weather_sources
from .helpers import get_forecast_result_dict

router = APIRouter()

_LOGGER = logging.getLogger("uvicorn")


@router.post("/{plant_name}/{interval}")
def post(
    plant_name: PVPlantNames,
    pv_system_mngr: Annotated[PVSystemManager, Depends(get_pv_system_mngr)],
    weather_api: Annotated[WeatherAPI, Depends(get_weather_sources)],
    start_end: StartEndRequest = None,
    interval: Interval = Interval.H1,
) -> ClearskyModel:
    """Get the estimated PV output power in Watts and energy in Wh at the given interval <interval> \
    for the given PV system <name>.

    POST: This will force a recalculation of the power output using the latest available weather data,\
    which may take some time.

    If no request body is provided, the first timestamp will be the current time and the last timestamp will be\
    the current time + interval.

    NB: Energy data is configured to represent the state at the beginning of the interval and what is going to happen \
    in this interval.

    :param plant_name: Name of the PV system
    :param interval: Interval of the returned data
    :return: Estimated PV power output in Watts at the given interval <interval> for the given PV system <name>
    """
    # for clearsky we don't care which weather API is used, so just use the first one
    weather_api = weather_api[0]

    # build the datetime index
    if start_end is None:
        _LOGGER.info(
            "No start and end timestamps provided, using current time and interval"
        )
        datetimes = weather_api.get_source_dates(
            weather_api.start_forecast, weather_api.end_forecast, interval
        )
    else:
        datetimes = weather_api.get_source_dates(
            start_end.start, start_end.end, interval
        )

    # convert datetimes to dataframe
    weather_df = pd.DataFrame(index=datetimes)

    # get the PV power output
    response_dict = get_forecast_result_dict(
        str(plant_name.name), pv_system_mngr, "clearsky", interval, weather_df
    )
    return ClearskyModel(**response_dict)
