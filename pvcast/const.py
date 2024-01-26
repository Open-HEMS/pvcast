"""Program global constants."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

DT_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

CONFIG_FILE_DEF = Path("config.yaml")
SECRETS_FILE_DEF = Path("secrets.yaml")

CONFIG_FILE_PATH = Path(os.environ.get("CONFIG_FILE_PATH", CONFIG_FILE_DEF))
SECRETS_FILE_PATH = Path(os.environ.get("SECRETS_FILE_PATH", SECRETS_FILE_DEF))

LOG_FORMAT = "%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)s)"
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
        "uvicorn.access": {"level": "INFO", "handlers": ["access"], "propagate": False},
    },
    "root": {"level": "DEBUG", "handlers": ["default"], "propagate": False},
}
