"""This module contains the FastAPI router for the /clearsky endpoint."""
from __future__ import annotations

import logging

import pandas as pd
from fastapi import APIRouter, Depends
from typing_extensions import Annotated

from ...model.forecasting import ForecastResult
from ...model.model import PVSystemManager
from ...weather.weather import WeatherAPI
from ..models.base import PowerInterval, PVPlantNames, StartEndRequest
from ..models.clearsky import ClearskyPowerModel
from ..routers.dependencies import get_pv_system_mngr, get_weather_api

router = APIRouter()

_LOGGER = logging.getLogger("uvicorn")


@router.post("/power/{plant_name}/{interval}")
def post(
    plant_name: PVPlantNames,
    pv_system_mngr: Annotated[PVSystemManager, Depends(get_pv_system_mngr)],
    weather_api: Annotated[WeatherAPI, Depends(get_weather_api)],
    start_end: StartEndRequest = None,
    interval: PowerInterval = PowerInterval.H1,
) -> ClearskyPowerModel:
    """Get the estimated PV power output in Watts at the given interval <interval> for the given PV system <name>.

    POST: This will force a recalculation of the power output using the latest available weather data,\
    which may take some time.

    If no request body is provided, the first timestamp will be the current time and the last timestamp will be\
    the current time + interval.

    :param plant_name: Name of the PV system
    :param interval: Interval of the returned data
    :return: Estimated PV power output in Watts at the given interval <interval> for the given PV system <name>
    """
    location = pv_system_mngr.location
    _LOGGER.info("Getting clearsky power for '%s'", plant_name)
    try:
        pvplant = pv_system_mngr.get_pv_plant(plant_name)
    except KeyError:
        _LOGGER.error("No PV system found with plant_name %s", plant_name)
        return {}

    if start_end is None:
        datetimes = weather_api.source_dates
    else:
        datetimes = pd.date_range(start=start_end.start, end=start_end.end, freq=interval, tz="UTC")

    # compute the clearsky power output for the given PV system and datetimes
    clearsky_output: ForecastResult = pvplant.clearsky.run(weather_df=datetimes)

    # convert ac power timestamps to string
    ac_power: pd.Series = clearsky_output.ac_power.copy().round(0).astype(int)
    ac_power.index = ac_power.index.strftime("%Y-%m-%dT%H:%M:%S%z")

    # build the response dict
    response_dict = {
        "plant_name": plant_name,
        "interval": interval,
        "start": ac_power.index[0],
        "end": ac_power.index[-1],
        "timezone": location.tz,
        "result": ac_power.to_dict(),
        "unit": "W",
    }

    return ClearskyPowerModel(**response_dict)
