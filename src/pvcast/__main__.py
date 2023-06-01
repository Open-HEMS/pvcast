"""Module that contains the command line application."""

from pathlib import Path
import logging

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
    config_reader = ConfigReader(Path("src/pvcast/config" + "/pv_config.yaml"))
    config = config_reader.config

    # create the PV model
    pv_model = PVModelChain(config["plant"], location=(52.35845515630293, 4.88115070391368))


if __name__ == "__main__":
    main()
