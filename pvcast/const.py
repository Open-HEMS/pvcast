"""Program global constants."""
from __future__ import annotations

from typing import Any

DT_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


LOG_FORMAT = "%(asctime)s [%(levelname)8s] %(message)s (%(name)s:%(lineno)s)"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

UVICORN_LOG_CONFIG: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {"format": LOG_FORMAT, "datefmt": DATE_FORMAT},
        "access": {"format": LOG_FORMAT, "datefmt": DATE_FORMAT},
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "uvicorn.error": {"level": "INFO", "handlers": ["default"], "propagate": False},
        "uvicorn.access": {
            "level": "WARNING",
            "handlers": ["access"],
            "propagate": False,
        },
    },
}
