"""Webserver unit tests."""
from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

import polars as pl
import pytest
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from pvcast.weather.weather import WeatherAPI

# define test data
mock_data_cs = pl.DataFrame(
    {
        "datetime": [
            "2020-01-01T00:00:00+00:00",
            "2020-01-01T00:30:00+00:00",
            "2020-01-01T01:00:00+00:00",
        ],
    }
)


@pytest.mark.parametrize("weather_api_fix_loc", mock_data_cs, indirect=True)
class TestWebserver:
    """Test base functions of the webserver."""

    def test_get_favicon(
        self,
        client: TestClient,
        weather_api_fix_loc: WeatherAPI,  # noqa: ARG002
    ) -> None:
        """Test getting the favicon."""
        response = client.get("/favicon.ico")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    def test_get_docs(
        self,
        client: TestClient,
        weather_api_fix_loc: WeatherAPI,  # noqa: ARG002
    ) -> None:
        """Test getting the docs."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        assert "PV Cast" in response.text


@pytest.mark.parametrize("weather_api_fix_loc", mock_data_cs, indirect=True)
@pytest.mark.parametrize("plant_name", ["EastWest", "South"])
@pytest.mark.parametrize("interval", ["1m", "5m", "15m", "30m", "1h"])
class TestClearsky:
    """Test the clearsky API."""

    def test_get_clearsky(
        self,
        client: TestClient,
        interval: str,
        plant_name: str,
        weather_api_fix_loc: WeatherAPI,  # noqa: ARG002
    ) -> None:
        """Test getting the clearsky forecast."""
        response = client.post(f"/clearsky/{plant_name}/{interval}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        response_dict = response.json()
        assert response_dict["interval"] == interval
        assert response_dict["plant_name"] == plant_name
        assert "clearskymodel" in response_dict
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

    @pytest.mark.parametrize(
        "start",
        [
            dt.datetime.now(dt.timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            ),
            None,
        ],
    )
    @pytest.mark.parametrize(
        "end",
        [
            dt.datetime.now(dt.timezone.utc).replace(
                hour=12, minute=59, second=0, microsecond=0
            ),
            None,
        ],
    )
    def test_get_clearsky_start_end(
        self,
        client: TestClient,
        start: dt.datetime | None,
        end: dt.datetime | None,
        interval: str,
        plant_name: str,
        weather_api_fix_loc: WeatherAPI,  # noqa: ARG002
    ) -> None:
        """Test getting the clearsky with a start date."""
        start_end = {}
        start_end.update({"start": start.isoformat()}) if start else None
        start_end.update({"end": end.isoformat()}) if end else None
        response = client.post(f"/clearsky/{plant_name}/{interval}", json=start_end)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        response_dict = response.json()
        resp_start = dt.datetime.fromisoformat(response_dict["start"])
        resp_end = dt.datetime.fromisoformat(response_dict["end"])
        if start:
            assert resp_start == start
        if end:
            assert resp_end <= end
