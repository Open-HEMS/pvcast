"""Program global constants."""

import os
from pathlib import Path

DT_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

CONFIG_FILE_DEF = Path("config.yaml")
SECRETS_FILE_DEF = Path("secrets.yaml")

CONFIG_FILE_PATH = Path(os.environ.get("CONFIG_FILE_PATH", CONFIG_FILE_DEF))
SECRETS_FILE_PATH = Path(os.environ.get("SECRETS_FILE_PATH", SECRETS_FILE_DEF))
