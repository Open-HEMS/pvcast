"""Script to retrieve inverter / PV module CSV files from PVLib and System Advisor Model (SAM) and merge
them into a single CSV file.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pvlib
from const import (
    INV_PROC_PATH,
    INV_PVLIB_PATH,
    INV_SAM_PATH,
    MANUAL_CORRECTIONS_INV,
    MOD_PROC_PATH,
    MOD_PVLIB_PATH,
    MOD_SAM_PATH,
)

_LOGGER = logging.getLogger(__name__)


def retrieve_sam_wrapper(path: Path) -> pd.DataFrame:
    """Retrieve SAM database.

    :param path: The path to the SAM database.
    :return: The SAM database as a pandas DataFrame.
    """
    if not path.exists():
        raise FileNotFoundError(f"Database {path} does not exist.")

    # retrieve database
    pv_df = pvlib.pvsystem.retrieve_sam(name=None, path=str(path))
    pv_df = pv_df.transpose()
    pv_df = pv_df.reset_index()
    return pv_df


def retrieve_and_merge(path1: Path, path2: Path) -> pd.DataFrame:
    """Retrieve SAM databases and merge them.

    :param path1: The first path to the SAM database.
    :param path2: The second path to the SAM database.
    :return: The merged SAM databases as a pandas DataFrame.
    """
    df1 = retrieve_sam_wrapper(path1)
    _LOGGER.info(f"{path1.name} length: {len(df1)}")

    df2 = retrieve_sam_wrapper(path2)
    _LOGGER.info(f"{path2.name} length: {len(df2)}")

    # merge databases
    merged_df = pd.concat([df1, df2], axis=0)

    # drop duplicates
    if merged_df.duplicated(subset=["index"]).any():
        _LOGGER.info(
            f"Dropping {len(merged_df[merged_df.duplicated(subset=['index'])])} duplicate entries for {path1.name}."
        )
        merged_df = merged_df.drop_duplicates(subset=["index"], keep="first")

    # sort in alphabetical order
    merged_df = merged_df.sort_values(by=["index"])

    return merged_df


def main() -> None:
    """Main function."""
    # configure logging
    logging.basicConfig(level=logging.DEBUG)
    fmt = "%(asctime)s %(levelname)s (%(threadName)s) " + "[%(name)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    # stdout handler
    logging.getLogger().handlers[0].setFormatter(
        logging.Formatter(fmt, datefmt=datefmt)
    )

    # print paths
    _LOGGER.info("INV_PVLIB_PATH: %s", INV_PVLIB_PATH)

    # retrieve and merge databases for inverters and modules
    inv_df = retrieve_and_merge(INV_PVLIB_PATH, INV_SAM_PATH)
    mod_df = retrieve_and_merge(MOD_PVLIB_PATH, MOD_SAM_PATH)

    # apply manual corrections
    for key, value in MANUAL_CORRECTIONS_INV.items():
        print(f"Got: {inv_df.loc[inv_df['index'] == key, list(value.keys())].head()}")
        inv_df.loc[inv_df["index"] == key, list(value.keys())] = list(value.values())

    # save databases
    inv_df.to_csv(INV_PROC_PATH, index=False)
    mod_df.to_csv(MOD_PROC_PATH, index=False)


if __name__ == "__main__":
    main()
