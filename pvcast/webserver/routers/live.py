"""This module contains the FastAPI router for the /live endpoint."""
from __future__ import annotations

import logging

import pandas as pd
from fastapi import APIRouter, Depends
from typing_extensions import Annotated

from ...model.model import PVSystemManager
from ...weather.weather import WeatherAPI
from ..models.base import Interval, PVPlantNames
from ..models.live import LiveModel
from ..routers.dependencies import get_pv_system_mngr, get_weather_api
from .helpers import get_forecast_result_dict

router = APIRouter()

_LOGGER = logging.getLogger("uvicorn")


@router.post("/{plant_name}/{interval}")
def post(
    plant_name: PVPlantNames,
    pv_system_mngr: Annotated[PVSystemManager, Depends(get_pv_system_mngr)],
    weather_api: Annotated[WeatherAPI, Depends(get_weather_api)],
    interval: Interval = Interval.H1,
) -> LiveModel:
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
    # get the weather data
    weather_dict: dict = weather_api.get_weather(calc_irrads=True)

    # convert to dataframe with datetime index
    weather_df = pd.DataFrame(weather_dict["data"])
    weather_df.index = pd.to_datetime(weather_df["datetime"])

    # get the PV power output
    response_dict = get_forecast_result_dict(
        str(plant_name.name), pv_system_mngr, "live", interval, weather_df
    )

    # add weather source from weather_dict to response_dict
    response_dict["weather_source"] = weather_dict["source"]
    return LiveModel(**response_dict)
