"""Script to retrieve CEC inverters and modules from PVLib and save them to CSV."""

import logging
import pathlib as pl

import pandas as pd
import pvlib
from const import INV_PVLIB_PATH, MOD_PVLIB_PATH

_LOGGER = logging.getLogger(__name__)


def get_cec_inverters() -> pd.DataFrame:
    """Retrieve CEC inverters from PVLib."""
    cec_inverters = pvlib.pvsystem.retrieve_sam("CECInverter")
    return cec_inverters


def get_cec_modules() -> pd.DataFrame:
    """Retrieve CEC modules from PVLib."""
    cec_modules = pvlib.pvsystem.retrieve_sam("CECMod")
    return cec_modules


def save_to_csv(data: pd.DataFrame, path: pl.Path) -> None:
    """Save datafram to CSV file."""
    cols = data.columns
    data = data.transpose()
    data["Name"] = cols

    # Move name to first column
    names = data["Name"]
    data.drop(labels=["Name"], axis=1, inplace=True)
    data.insert(0, "Name", names)

    data.to_csv(path, index=False)


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

    cec_inverters = get_cec_inverters()
    cec_modules = get_cec_modules()

    # Save data to CSV files
    _LOGGER.info("Saving PVLib CEC inverters to %s", INV_PVLIB_PATH)
    save_to_csv(cec_inverters, INV_PVLIB_PATH)
    _LOGGER.info("Saving PVLib CEC modules to %s", MOD_PVLIB_PATH)
    save_to_csv(cec_modules, MOD_PVLIB_PATH)
    _LOGGER.info("Done.")


if __name__ == "__main__":
    main()
