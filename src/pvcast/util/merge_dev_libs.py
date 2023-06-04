"""
Script to retrieve inverter / PV module CSV files from PVLib and System Advisor Model (SAM) and merge
them into a single CSV file.
"""

import logging
from pathlib import Path

import pandas as pd
import pvlib

RAW_DATA_PATH = Path(__file__).parent.parent / "data/raw"
INV_PVLIB_PATH = RAW_DATA_PATH / "cec_inverters_pvlib.csv"
INV_SAM_PATH = RAW_DATA_PATH / "cec_inverters_sam.csv"
MOD_PVLIB_PATH = RAW_DATA_PATH / "cec_modules_pvlib.csv"
MOD_SAM_PATH = RAW_DATA_PATH / "cec_modules_sam.csv"

PROC_DATA_PATH = Path(__file__).parent.parent / "data/proc"

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
    inv_df.to_csv(PROC_DATA_PATH / "cec_inverters.csv", index=False)
    mod_df.to_csv(PROC_DATA_PATH / "cec_modules.csv", index=False)


if __name__ == "__main__":
    main()
