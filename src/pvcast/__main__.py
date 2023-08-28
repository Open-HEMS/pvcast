"""Module that contains the command line application."""

from __future__ import annotations

import logging
from pathlib import Path

from .config.configreader import ConfigReader
from .webserver.webserver import WebServer


def init_logger():
    """Initialize python logger."""
    logging.basicConfig(level=logging.DEBUG)
    fmt = "%(asctime)s %(levelname)s (%(threadName)s) " + "[%(name)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    # stdout handler
    logging.getLogger().handlers[0].setFormatter(logging.Formatter(fmt, datefmt=datefmt))


def main():
    """Entry point for the application script"""

    # initialize logger
    init_logger()

    # create config reader
    config_path = Path("config.yaml")
    secrets_path = Path("secrets.yaml")
    config_reader = ConfigReader(config_path, secrets_path)

    # create webserver
    webserver = WebServer(config_reader=config_reader)
    webserver.run()


if __name__ == "__main__":
    main()
