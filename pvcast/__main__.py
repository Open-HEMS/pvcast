"""Module that contains the command line application."""

from __future__ import annotations

import logging
import os
from typing import Any

import uvicorn

from pvcast.commandline.commandline import get_args

_LOGGER = logging.getLogger(__name__)


def init_logger(log_level: int = logging.INFO) -> None:
    """Initialize python logger."""
    fmt = "%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)s)"
    datefmt = "%Y-%m-%d %H:%M:%S"

    # set the application logger
    logging.basicConfig(level=log_level, format=fmt, datefmt=datefmt)

    # stdout handler
    logging.getLogger().handlers[0].setFormatter(
        logging.Formatter(fmt, datefmt=datefmt)
    )


def main() -> None:
    """Entry point for the application script."""
    args: dict[str, Any] = get_args()

    # set config file paths as environment variables
    os.environ["CONFIG_FILE_PATH"] = str(args["config"])
    if args["secrets"]:
        os.environ["SECRETS_FILE_PATH"] = str(args["secrets"])

    # initialize logger
    init_logger(args["log_level"])
    _LOGGER.info("Starting pvcast webserver ... log level: %s", args["log_level"])

    # start uvicorn server
    uvicorn.run(
        "pvcast.webserver.app:app",
        host=args["host"],
        port=args["port"],
        reload=False,
        workers=args["workers"],
        log_level=logging.getLevelName(args["log_level"]).lower(),
    )


if __name__ == "__main__":
    main()
