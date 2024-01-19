"""Webserver unit tests."""
from __future__ import annotations

import datetime as dt
import urllib.parse
from typing import TYPE_CHECKING

import numpy as np
import polars as pl
import pytest
from fastapi.testclient import TestClient

from tests.const import MOCK_WEATHER_API

if TYPE_CHECKING:
    from pvcast.weather.weather import WeatherAPI

n_points = int(dt.timedelta(hours=10) / dt.timedelta(hours=1))
mock_data = pl.DataFrame(
    {
        "datetime": pl.datetime_range(
            dt.datetime.now(dt.timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            ),
            dt.datetime.now(dt.timezone.utc).replace(
                hour=23, minute=59, second=0, microsecond=0
            ),
            "1h",
            eager=True,
            time_zone="UTC",
        )[0:n_points],
        "cloud_cover": list(np.linspace(20, 60, n_points)),
        "wind_speed": list(np.linspace(0, 10, n_points)),
        "temperature": list(np.linspace(10, 25, n_points)),
        "humidity": list(np.linspace(0, 100, n_points)),
    }
)


class TestWebserver:
    """Test base functions of the webserver."""

    def test_get_favicon(
        self,
        client_base: TestClient,
    ) -> None:
        """Test getting the favicon."""
        response = client_base.get("/favicon.ico")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    def test_get_docs(
        self,
        client_base: TestClient,
    ) -> None:
        """Test getting the docs."""
        response = client_base.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        assert "PV Cast" in response.text

    def test_get_list_endpoints(
        self,
        client_base: TestClient,
    ) -> None:
        """Test getting the list of endpoints."""
        response = client_base.get("/utils/list_endpoints/")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert len(response.json()) > 0


@pytest.mark.parametrize("weather_api_fix_loc", [mock_data], indirect=True)
@pytest.mark.parametrize("plant_name", ["EastWest", "South"])
@pytest.mark.parametrize("interval", ["1m", "5m", "15m", "30m", "1h"])
class CommonForecastTests:
    """Common tests for the forecast API."""

    fc_type: str
    weather_source: str | None = None

    @pytest.mark.parametrize("start", [mock_data["datetime"][n_points // 4], None])
    @pytest.mark.parametrize("end", [mock_data["datetime"][n_points // 2], None])
    def test_get_forecast_start_end(
        self,
        client: TestClient,
        start: dt.datetime | None,
        end: dt.datetime | None,
        interval: str,
        plant_name: str,
        weather_api_fix_loc: WeatherAPI,  # noqa: ARG002
    ) -> None:
        """Test getting the clearsky with a start date."""
        # build url
        url = f"/{self.fc_type}/{plant_name}/{interval}"
        url += f"/{self.weather_source}" if self.weather_source else ""
        url += f"?start={urllib.parse.quote(start.isoformat())}" if start else ""
        url += "&" if start and end else ""
        url += "?" if not start and end else ""
        url += f"end={urllib.parse.quote(end.isoformat())}" if end else ""

        # send request
        response = client.get(url)

        # check response
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        response_dict = response.json()
        resp_start = dt.datetime.fromisoformat(response_dict["start"])
        resp_end = dt.datetime.fromisoformat(response_dict["end"])
        if start:
            assert resp_start == start
        if end:
            assert resp_end <= end
        assert response_dict["interval"] == interval
        assert response_dict["plant_name"] == plant_name
        assert "start" in response_dict
        assert "end" in response_dict
        assert "timezone" in response_dict
        assert "interval" in response_dict
        assert "period" in response_dict
        assert isinstance(response_dict["period"], list)
        assert len(response_dict["period"]) > 0
        assert "datetime" in response_dict["period"][0]
        assert "watt" in response_dict["period"][0]
        assert "watt_cumsum" in response_dict["period"][0]
        assert isinstance(response_dict["period"][0]["datetime"], str)
        assert isinstance(response_dict["period"][0]["watt"], int)
        assert isinstance(response_dict["period"][0]["watt_cumsum"], int)
        assert (
            response_dict["period"][0]["watt_cumsum"]
            == response_dict["period"][0]["watt"]
        )


class TestClearsky(CommonForecastTests):
    """Test the clearsky API."""

    fc_type = "clearsky"


class TestLive(CommonForecastTests):
    """Test the live API."""

    fc_type = "live"
    weather_source = MOCK_WEATHER_API
