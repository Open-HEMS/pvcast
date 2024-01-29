"""Module that contains the command line application."""

from __future__ import annotations

import logging
from typing import Any

import uvicorn

from pvcast.commandline.commandline import get_args
from pvcast.const import DATE_FORMAT, LOG_FORMAT, UVICORN_LOG_CONFIG

_LOGGER = logging.getLogger(__name__)


def init_logger(log_level: int = logging.INFO) -> None:
    """Initialize python logger."""
    fmt = LOG_FORMAT
    datefmt = DATE_FORMAT

    # set the application logger
    logging.basicConfig(level=log_level, format=fmt, datefmt=datefmt, force=True)

    # set log level of imported modules
    logging.getLogger("solara").setLevel(logging.WARNING)
    logging.getLogger("reacton").setLevel(logging.WARNING)


def main() -> None:
    """Entry point for the application script."""
    args: dict[str, Any] = get_args()

    # initialize logger
    init_logger(args["log_level"])
    _LOGGER.info(
        "Starting pvcast webserver ... log level: %s",
        logging.getLevelName(args["log_level"]),
    )

    # start uvicorn server
    uvicorn.run(
        "pvcast.webserver.app:app",
        host=args["host"],
        port=args["port"],
        reload=False,
        workers=args["workers"],
        log_config=UVICORN_LOG_CONFIG,
    )


if __name__ == "__main__":
    main()
