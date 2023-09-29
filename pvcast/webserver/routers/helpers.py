"""Helper functions for the webserver."""
import json
import logging
from collections import OrderedDict
from typing import Any

import numpy as np
import pandas as pd
from pandas.core.indexes.multi import MultiIndex

from ...model.forecasting import ForecastResult, PowerEstimate
from ...model.model import PVSystemManager

_LOGGER = logging.getLogger("uvicorn")


def _np_encoder(obj: Any) -> np.generic:
    """Encode numpy types to python types."""
    if isinstance(obj, np.generic):
        return obj.item()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def multi_idx_to_nested_dict(data: pd.DataFrame, value_only=False) -> OrderedDict:
    """Convert a multiindex dataframe to a nested dict. Kudos to dcragusa.

    :param df: Multiindex dataframe
    :param value_only: If true, only return the values of the dataframe
    :return: Nested dict
    """
    if isinstance(data.index, MultiIndex):
        return OrderedDict(
            (k, multi_idx_to_nested_dict(data.loc[k])) for k in data.index.remove_unused_levels().levels[0]
        )
    if value_only:
        return OrderedDict((k, data.loc[k].values[0]) for k in data.index)
    odict = OrderedDict()
    for idx in data.index:
        d_col = OrderedDict()
        for col in data.columns:
            d_col[col] = data.loc[idx, col]
        odict[idx] = d_col
    return json.loads(json.dumps(odict, default=_np_encoder))


def get_forecast_result_dict(
    plant_name: str,
    pv_system_mngr: PVSystemManager,
    fc_type: str,
    interval: str,
    weather_df: pd.DataFrame = None,
) -> dict:
    """Convert the forecast result to a nested dict.

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

    # build multi-index columns
    cols = [("watt", pv_plant) for pv_plant in pv_plant_names]
    cols += [("watt_hours", pv_plant) for pv_plant in pv_plant_names]
    cols += [("watt_hours_cumsum", pv_plant) for pv_plant in pv_plant_names]
    cols += [("watt_hours", "Total")] if all_arg else []
    cols += [("watt_hours_cumsum", "Total")] if all_arg else []
    cols += [("watt", "Total")] if all_arg else []
    multi_index = pd.MultiIndex.from_tuples(cols, names=["type", "plant"])

    # build the result dataframe
    result_df = pd.DataFrame(columns=multi_index)

    # loop over all PV plants and compute the clearsky power output
    for pv_plant in pv_plant_names:
        _LOGGER.info("Estimating clearsky performance for plant: %s", pv_plant)

        # compute the PV output for the given PV system and datetimes
        try:
            pvplant = pv_system_mngr.get_pv_plant(pv_plant)
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

        # resample the output to the given interval
        output = output.resample(interval)

        # convert ac power timestamps to string
        ac_power: pd.Series = output.ac_power
        ac_energy: pd.Series = output.ac_energy
        ac_power.index = ac_power.index.strftime("%Y-%m-%dT%H:%M:%S%z")
        ac_energy.index = ac_energy.index.strftime("%Y-%m-%dT%H:%M:%S%z")

        # build the output dataframe with multi-index
        result_df[("watt", pv_plant)] = ac_power
        result_df[("watt_hours", pv_plant)] = ac_energy
        result_df[("watt_hours_cumsum", pv_plant)] = ac_energy.cumsum()

    # if all_arg, sum the power and energy columns
    if all_arg:
        result_df[("watt", "Total")] = result_df["watt"].sum(axis=1)
        result_df[("watt_hours", "Total")] = result_df["watt_hours"].sum(axis=1)
        result_df[("watt_hours_cumsum", "Total")] = result_df["watt_hours_cumsum"].sum(axis=1)

    # check if there are any NaN values in the result
    if result_df.isnull().values.any():
        raise ValueError(f"NaN values in the result dataframe: \n{result_df}")

    # round all columns and set all values to int64
    result_df = result_df.round(0).astype(int)
    response_dict = {
        "start": result_df.index[0],
        "end": result_df.index[-1],
        "interval": interval,
        "timezone": "UTC",
    }

    # convert the result dataframe to a nested dict
    result_df = dict(multi_idx_to_nested_dict(result_df.T))
    response_dict.update({"result": result_df})
    return response_dict
