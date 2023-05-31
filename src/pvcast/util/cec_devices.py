"""Script to retrieve CEC inverters and modules from PVLib."""

from __future__ import annotations

import pathlib as pl

import pandas as pd
import pvlib


def get_cec_inverters():
    """Retrieve CEC inverters from PVLib."""
    cec_inverters = pvlib.pvsystem.retrieve_sam("CECInverter")
    return cec_inverters


def get_cec_modules():
    """Retrieve CEC modules from PVLib."""
    cec_modules = pvlib.pvsystem.retrieve_sam("CECMod")
    return cec_modules


def save_to_csv(data: pd.DataFrame, path: pl.Path, transpose: bool = False):
    """Save datafram to CSV files."""

    if transpose:
        cols = data.columns
        data = data.transpose()
        data["Name"] = cols

        # Move name to first column
        names = data["Name"]
        data.drop(labels=["Name"], axis=1, inplace=True)
        data.insert(0, "Name", names)

    data.to_csv(path, index=False)


def main():
    """Main function."""
    cec_inverters = get_cec_inverters()
    cec_modules = get_cec_modules()

    # Create data directory if it does not exist
    data_path = pl.Path("data")
    data_path.mkdir(exist_ok=True)

    # Save data to CSV files
    save_to_csv(cec_inverters, data_path / "cec_inverters.csv", transpose=True)
    save_to_csv(cec_modules, data_path / "cec_modules.csv", transpose=True)


if __name__ == "__main__":
    main()
