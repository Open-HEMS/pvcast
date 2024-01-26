"""Commandline interface for pvcast."""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Any


def _check_file_exists(path: Path) -> Path:
    """Check if file exists."""
    if not isinstance(path, Path):
        msg = f"{path} is not a valid path.)"
        raise argparse.ArgumentTypeError(msg)
    if not path.exists():
        msg = f"{path} does not exist."
        raise argparse.ArgumentTypeError(msg)
    if not path.is_file():
        msg = f"{path} is not a file."
        raise argparse.ArgumentTypeError(msg)
    return path


def get_args() -> dict[str, Any]:
    """Retrieve arguments from commandline."""
    parser = argparse.ArgumentParser(description="pvcast webserver")
    parser.add_argument(
        "-l",
        "--log-level",
        help="Set application-wide log level.",
        default="INFO",
        type=str,
    )
    parser.add_argument(
        "-c", "--config", help="Configuration file path.", type=Path, required=True
    )
    parser.add_argument(
        "-s",
        "--secrets",
        help="Secrets file path. Must be provided if !secret tags are used.",
        type=Path,
    )
    parser.add_argument(
        "-w",
        "--workers",
        help="Number of workers to execute uvicorn server with.",
        default=1,
        type=int,
    )
    parser.add_argument("--host", help="API host URL.", default="127.0.0.1", type=str)
    parser.add_argument("--port", help="API host port number.", default=4557, type=int)

    # parse arguments
    args = vars(parser.parse_args())

    # check if config files exist
    os.environ["CONFIG_FILE_PATH"] = str(_check_file_exists(args["config"]))
    if secrets := args.get("secrets"):
        os.environ["SECRETS_FILE_PATH"] = str(_check_file_exists(secrets))

    # pre-processing of arguments
    args["log_level"] = getattr(logging, args["log_level"].upper(), None)
    return args
