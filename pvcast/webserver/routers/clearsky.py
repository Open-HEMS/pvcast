"""This module contains the FastAPI router for the /clearsky endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..models.base import Interval
from ..models.clearsky import ClearskyPowerModel

# from ...model.forecasting

router = APIRouter()


@router.get("/power/{name}/{interval}")
def get(name: str, interval: Interval = "1H") -> ClearskyPowerModel:
    """Get the estimated PV power output in Watts at the given interval <interval> for the given PV system <name>.

    GET: Will return 404 if no data is available. This should be used as a fast, cached alternative of the POST\
    method.

    :param name: Name of the PV system
    :param interval: Interval of the returned data
    :return: Estimated PV power output in Watts at the given interval <interval> for the given PV system <name>
    """
    return {}


@router.post("/power/{name}/{interval}")
def post(name: str, interval: Interval = "1H") -> ClearskyPowerModel:
    """Get the estimated PV power output in Watts at the given interval <interval> for the given PV system <name>.

    POST: This will force a recalculation of the power output using the latest available weather data,\
    which may take some time.

    :param name: Name of the PV system
    :param interval: Interval of the returned data
    :return: Estimated PV power output in Watts at the given interval <interval> for the given PV system <name>
    """
    return {}
