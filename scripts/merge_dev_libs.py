"""
Script to retrieve inverter / PV module CSV files from PVLib and System Advisor Model (SAM) and merge
them into a single CSV file.
"""

import logging
from pathlib import Path

import pandas as pd
import pvlib
from const import (INV_PROC_PATH, INV_PVLIB_PATH, INV_SAM_PATH, MOD_PROC_PATH,
                   MOD_PVLIB_PATH, MOD_SAM_PATH)

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


def main():
    """Main function."""
    # configure logging
    logging.basicConfig(level=logging.DEBUG)
    fmt = "%(asctime)s %(levelname)s (%(threadName)s) " + "[%(name)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    # stdout handler
    logging.getLogger().handlers[0].setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    # print paths
    _LOGGER.info("INV_PVLIB_PATH: %s", INV_PVLIB_PATH)

    # merge PVLib and SAM databases
    pvlib_inv_df = retrieve_sam_wrapper(INV_PVLIB_PATH)
    _LOGGER.info("pvlib_inv_df length: %s", len(pvlib_inv_df))
    sam_inv_df = retrieve_sam_wrapper(INV_SAM_PATH)
    _LOGGER.info("sam_inv_df length: %s", len(sam_inv_df))
    pvlib_mod_df = retrieve_sam_wrapper(MOD_PVLIB_PATH)
    _LOGGER.info("pvlib_mod_df length: %s", len(pvlib_mod_df))
    sam_mod_df = retrieve_sam_wrapper(MOD_SAM_PATH)
    _LOGGER.info("sam_mod_df length: %s", len(sam_mod_df))

    # merge databases
    inv_df = pd.concat([pvlib_inv_df, sam_inv_df], axis=0)
    mod_df = pd.concat([pvlib_mod_df, sam_mod_df], axis=0)

    # drop duplicates
    if inv_df.duplicated(subset=["index"]).any():
        _LOGGER.info("Dropping %s duplicate inverters.", len(inv_df[inv_df.duplicated(subset=["index"])]))
        inv_df = inv_df.drop_duplicates(subset=["index"], keep="first")
    if mod_df.duplicated(subset=["index"]).any():
        _LOGGER.info("Dropping %s duplicate modules.", len(mod_df[mod_df.duplicated(subset=["index"])]))
        mod_df = mod_df.drop_duplicates(subset=["index"], keep="first")

    # sort in alphabetical order
    inv_df = inv_df.sort_values(by=["index"])
    mod_df = mod_df.sort_values(by=["index"])

    # save databases
    inv_df.to_csv(INV_PROC_PATH, index=False)
    mod_df.to_csv(MOD_PROC_PATH, index=False)


if __name__ == "__main__":
    main()
