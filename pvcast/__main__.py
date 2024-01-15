"""Module that contains the command line application."""

from __future__ import annotations

import logging

import uvicorn

from .webserver.const import PORT, WEBSERVER_URL

_LOGGER = logging.getLogger(__name__)


def init_logger() -> None:
    """Initialize python logger."""
    logging.basicConfig(level=logging.DEBUG)
    fmt = "%(asctime)s %(levelname)s (%(threadName)s) " + "[%(name)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    # stdout handler
    logging.getLogger().handlers[0].setFormatter(
        logging.Formatter(fmt, datefmt=datefmt)
    )


def main() -> None:
    """Entry point for the application script"""
    # initialize logger
    init_logger()
    _LOGGER.info("Starting pvcast webserver")

    # start uvicorn server
    uvicorn.run(
        "pvcast.webserver.app:app",
        host=WEBSERVER_URL,
        port=PORT,
        reload=True,
        workers=3,
        reload_includes=["*.yaml", "*.yml"],
    )


if __name__ == "__main__":
    main()
