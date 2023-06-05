"""Module that contains the command line application."""

import logging
from pathlib import Path

from .config.configreader import ConfigReader
from .model.pvmodel import PVModelChain


def init_logger():
    """Initialize python logger."""
    logging.basicConfig(level=logging.DEBUG)
    fmt = "%(asctime)s %(levelname)s (%(threadName)s) " + "[%(name)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    # stdout handler
    logging.getLogger().handlers[0].setFormatter(logging.Formatter(fmt, datefmt=datefmt))


def main():
    """Entry point for the application script"""
    init_logger()

    # read the configuration
    config_reader = ConfigReader(Path("src/pvcast/config" + "/pv_config_se.yaml"))
    config = config_reader.config
    lat = config["general"]["location"]["latitude"]
    lon = config["general"]["location"]["longitude"]
    alt = config["general"]["location"]["altitude"]

    # create the PV model
    model_chain = PVModelChain(config["plant"], location=(lat, lon), altitude=alt)

    # get the PV model
    model = model_chain.pv_model
    print(model)


if __name__ == "__main__":
    main()
