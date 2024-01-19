from __future__ import annotations

from pathlib import Path

LOC_EUW = (52.3585, 4.8810, "Europe/Amsterdam", 0.0)
LOC_USW = (40.7211, -74.0701, "America/New_York", 10.0)
LOC_AUS = (-31.9741, 115.8517, "Australia/Perth", 0.0)

TEST_CONF_PATH_SEC = Path(__file__).parent / "unit" / "test_config_sec.yaml"
TEST_CONF_PATH_NO_SEC = Path(__file__).parent / "unit" / "test_config_no_sec.yaml"
TEST_CONF_PATH_ERROR = Path(__file__).parent / "unit" / "test_config_error.yaml"
TEST_CONF_PATH_MISSING_SEC = (
    Path(__file__).parent / "unit" / "test_config_missing_sec.yaml"
)
TEST_SECRETS_PATH = Path(__file__).parent / "unit" / "test_secrets.yaml"

HASS_TEST_URL = "192.168.1.217:8123"
HASS_TEST_TOKEN = """eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJhMTI1Mzg4MTVlZDk0M\
zRmODQ0YjJmMGIzZDc1MGVmOSIsImlhdCI6MTcwMTQ0MjQwNywiZXhwIjoyMDE2ODAyNDA3fQ.KkHCfCuFdkUyP\
b3LNA8HcEvIH2IQ1rmtSDn3haGbKeM"""
HASS_WEATHER_ENTITY_ID = "weather.forecast_thuis"

# this must be one of the keys in the config file due to
# get_weather_sources in file pvcast/webserver/models/live.py
MOCK_WEATHER_API = "ClearOutside"
