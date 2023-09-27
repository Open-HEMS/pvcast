"""Helper functions for the webserver."""
from collections import OrderedDict
import json
from typing import Any
import pandas as pd
from pandas.core.indexes.multi import MultiIndex
import numpy as np


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
