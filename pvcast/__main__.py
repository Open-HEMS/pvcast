"""Module that contains the command line application."""

from __future__ import annotations

import logging
from pathlib import Path

import uvicorn

from .config.configreader import ConfigReader
from .webserver.const import PORT, WEBSERVER_URL

_LOGGER = logging.getLogger(__name__)


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

    # get config as dict
    _LOGGER.info("Loaded configuration file from path %s: \n%s", config_path, config_reader.config)

    # start uvicorn server
    uvicorn.run("pvcast.webserver.app:app", host=WEBSERVER_URL, port=PORT, reload=True, workers=3)


if __name__ == "__main__":
    main()
