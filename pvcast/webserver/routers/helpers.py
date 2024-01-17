"""Helper functions for the webserver."""
from __future__ import annotations

import logging
from typing import Any

import polars as pl

from ...const import DT_FORMAT
from ...model.forecasting import ForecastResult, PowerEstimate
from ...model.model import PVSystemManager
from ...webserver.models.base import Interval

_LOGGER = logging.getLogger("uvicorn")


def get_forecast_result_dict(
    plant_name: str,
    pv_system_mngr: PVSystemManager,
    fc_type: str,
    interval: Interval,
    weather_df: pl.DataFrame = None,
) -> dict[str, Any]:
    """Use the weather data to compute the estimated PV output power in Watts at the \
    given interval <interval> for the given PV system <name>.

    :param plant_name: Name of the PV system
    :param pv_system_mngr: PV system manager
    :param fc_type: Forecasting algorithm type
    :param interval: Interval of the returned data
    :param weather_df: Weather dataframe
    :return: Nested dict
    """
    # loop over all PV plants and find the one with the given name
    all_arg = plant_name.lower() == "all"
    pv_plant_names = list(pv_system_mngr.pv_plants.keys()) if all_arg else [plant_name]

    # loop over all PV plants and compute the estimated power output
    ac_w_period = pl.DataFrame()
    for pv_plant in pv_plant_names:
        _LOGGER.info("Calculating PV output for plant: %s", pv_plant)

        # compute the PV output for the given PV system and datetimes
        try:
            pvplant = pv_system_mngr.get_pv_plant(pv_plant)
            _LOGGER.info("PV plant found: %s", pv_plant)
        except KeyError:
            _LOGGER.error("No PV system found with plant_name %s", plant_name)
            continue

        # run forecasting algorithm
        try:
            pv_plant_type: PowerEstimate = getattr(pvplant, fc_type)
        except AttributeError:
            _LOGGER.error("No forecasting algorithm found with name %s", fc_type)
            continue
        output: ForecastResult = pv_plant_type.run(weather_df=weather_df)

        # upsample the output to the requested interval
        ac_w_period = ac_w_period.with_columns(
            output.upsample(interval).ac_power.rename({"ac_power": f"watt_{pv_plant}"})
        )
        ac_w_period = ac_w_period.with_columns(
            ac_w_period[f"watt_{pv_plant}"]
            .cast(pl.Float64)
            .round(0)
            .clip(0)
            .cast(pl.Int64)
        )

    # horizontally sum the power columns
    ac_w_period = ac_w_period.select(
        "datetime",
        pl.sum_horizontal(pl.exclude("datetime")).cast(pl.Int64).alias("watt"),
    )

    # cumulatively sum the power column
    ac_w_period = ac_w_period.with_columns(
        ac_w_period["watt"].cum_sum().alias("watt_cumsum")
    )

    # truncate datetimes to the requested interval
    ac_w_period = ac_w_period.with_columns(
        pl.col("datetime").dt.truncate(interval.value)
    )

    # construct the response dict
    response_dict = {
        "start": ac_w_period["datetime"].min().strftime(DT_FORMAT),
        "end": ac_w_period["datetime"].max().strftime(DT_FORMAT),
        "forecast_type": fc_type,
        "plant_name": plant_name,
        "interval": interval.value,
        "timezone": "UTC",
        "period": ac_w_period.with_columns(
            pl.col("datetime").dt.strftime(DT_FORMAT)
        ).to_dicts(),
    }
    return response_dict
