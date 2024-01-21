"""Commandline interface for pvcast."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any


def _check_file_exists(path: Path) -> Path:
    """Check if file exists."""
    if not path.exists():
        msg = f"{path} does not exist."
        raise argparse.ArgumentTypeError(msg)
    return path


def get_args() -> dict[str, Any]:
    """Retrieve arguments from commandline."""
    parser = argparse.ArgumentParser(description="pvcast webserver")
    parser.add_argument(
        "-l", "--log-level", help="set log level", default="INFO", type=str
    )
    parser.add_argument(
        "-c", "--config", help="config file path", default="config.yaml", type=Path
    )
    parser.add_argument("-s", "--secrets", help="secrets file path", type=Path)
    parser.add_argument(
        "-w", "--workers", help="number of workers", default=3, type=int
    )
    parser.add_argument("--host", help="host url", default="127.0.0.1", type=str)
    parser.add_argument("--port", help="port number", default=4557, type=int)

    # get arguments
    args_ns = parser.parse_args()
    args = vars(args_ns)

    # check if config files exist
    args["config"] = _check_file_exists(args["config"])
    if secrets := args.get("secrets"):
        args["secrets"] = _check_file_exists(secrets)

    # pre-processing of arguments
    args["log_level"] = getattr(logging, args["log_level"].upper(), None)
    return args
