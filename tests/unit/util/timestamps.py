"""Test timestamp (datetime) utilities."""
from __future__ import annotations

from datetime import timedelta

import pytest

from pvcast.util.timestamps import timedelta_to_pl_duration


class TestUtilTimestamps:
    """Test timestamp utilities."""

    @pytest.mark.parametrize(
        ("td", "expected"),
        [
            (timedelta(days=1), "1d"),
            (timedelta(days=-1), "-1d"),
            (timedelta(seconds=1), "1s"),
            (timedelta(seconds=-1), "-1s"),
            (timedelta(microseconds=1), "1us"),
            (timedelta(microseconds=-1), "-1us"),
            (timedelta(days=1, seconds=1), "1d1s"),
            (timedelta(days=-1, seconds=-1), "-1d1s"),
            (timedelta(days=1, microseconds=1), "1d1us"),
            (timedelta(days=-1, microseconds=-1), "-1d1us"),
            (None, None),
        ],
    )
    def test_timedelta_to_pl_duration(self, td: timedelta, expected: str) -> None:
        out = timedelta_to_pl_duration(td)
        assert out == expected
