"""Commandline interface for pvcast unit tests."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from pvcast.commandline.commandline import _check_file_exists, get_args


class TestCommandline:
    """Test the commandline module."""

    @pytest.fixture
    def mock_args(self, request: pytest.FixtureRequest) -> dict[str, Any]:
        """Mock command line arguments."""
        params = {
            "log_level": "DEBUG",
            "config": "test_config.yaml",
            "workers": 5,
            "host": "localhost",
            "port": 8080,
        }
        return {**params, **request.param} if request.param else params

    def test_check_file_exists_existing_file(self, tmp_path: Path) -> None:
        """Test if _check_file_exists returns the file path if the file exists."""
        file_path = tmp_path / "existing_file.txt"
        file_path.touch()
        result = _check_file_exists(file_path)
        assert result == file_path

    def test_check_file_exists_non_existing_file(self, tmp_path: Path) -> None:
        """Test if _check_file_exists raises an error if the file does not exist."""
        non_existing_file = tmp_path / "non_existing_file.txt"
        with pytest.raises(argparse.ArgumentTypeError, match="does not exist"):
            _check_file_exists(non_existing_file)

    def test_check_file_exists_directory(self, tmp_path: Path) -> None:
        """Test if _check_file_exists raises an error if the path is a directory."""
        directory = tmp_path / "directory"
        directory.mkdir()
        with pytest.raises(argparse.ArgumentTypeError, match="is not a file"):
            _check_file_exists(directory)

    def test_check_file_exists_not_path(self) -> None:
        """Test if _check_file_exists raises an error if the path is not a Path object."""
        with pytest.raises(argparse.ArgumentTypeError, match="is not a valid path"):
            _check_file_exists("not_a_path")  # type: ignore[arg-type]

    @patch("argparse.ArgumentParser.parse_args")
    @patch("pvcast.commandline.commandline._check_file_exists")
    @pytest.mark.parametrize(
        "mock_args", [{}, {"secrets": "test_secrets.yaml"}], indirect=True
    )
    def test_get_args(
        self,
        mock_check_file_exists: MagicMock,
        mock_parse_args: MagicMock,
        mock_args: dict[str, Any],
    ) -> None:
        """Test if get_args returns the correct arguments."""
        # mocking the command line arguments
        mock_parse_args.return_value = argparse.Namespace(**mock_args)

        # mocking the _check_file_exists function
        mock_check_file_exists.side_effect = lambda x: Path(x)

        args = get_args()

        # assertions
        assert args["log_level"] == logging.DEBUG
        assert args["config"] == "test_config.yaml"
        assert (
            args["secrets"] == "test_secrets.yaml" if "secrets" in mock_args else True
        )
        assert args["workers"] == 5
        assert args["host"] == "localhost"
        assert args["port"] == 8080

        # ensure _check_file_exists is called with the correct arguments
        calls = [
            call("test_config.yaml"),
        ]
        if "secrets" in mock_args:
            calls.append(call("test_secrets.yaml"))
        mock_check_file_exists.assert_has_calls(calls, any_order=True)
