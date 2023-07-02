from __future__ import annotations

from pathlib import Path

LOC_EUW = (52.3585, 4.8810, "Europe/Amsterdam", 0.0)
LOC_USW = (40.6893, -74.0445, "America/New_York", 0.0)
LOC_AUS = (-31.9741, 115.8517, "Australia/Perth", 0.0)

TEST_CONF_PATH_SEC = Path(__file__).parent.parent / "tests" / "test_config_sec.yaml"
TEST_CONF_PATH_NO_SEC = Path(__file__).parent.parent / "tests" / "test_config_no_sec.yaml"
TEST_CONF_PATH_ERROR = Path(__file__).parent.parent / "tests" / "test_config_error.yaml"
TEST_SECRETS_PATH = Path(__file__).parent.parent / "tests" / "test_secrets.yaml"

HASS_TEST_URL = "http://localhost:8123"
HASS_TEST_TOKEN = """eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI5MGZiN2I2OGVlODk0ZDk3ODMyMGQ5MjRlMzExM2YxNyIsImlhd\
CI6MTY4ODI1MTk3OCwiZXhwIjoyMDAzNjExOTc4fQ.EHOvN2SCydnvY6lYGIvN_eAujYXu5SlawlUCMc39D1Y"""
