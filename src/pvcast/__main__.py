"""Module that contains the command line application."""

import logging
from pathlib import Path

from .webserver.webserver import run


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

    # run webserver
    config_path = Path("config.yaml")
    secrets_path = Path("secrets.yaml")
    run(config_path, secrets_path)


if __name__ == "__main__":
    main()
