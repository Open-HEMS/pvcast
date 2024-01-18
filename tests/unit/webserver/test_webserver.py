"""Webserver unit tests."""
from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

import polars as pl
import pytest
from fastapi.testclient import TestClient

from tests.const import MOCK_WEATHER_API

if TYPE_CHECKING:
    from pvcast.weather.weather import WeatherAPI


mock_data = pl.DataFrame(
    {
        "datetime": [
            "2020-01-01T00:00:00+00:00",
            "2020-01-01T01:00:00+00:00",
            "2020-01-01T02:00:00+00:00",
            "2020-01-01T03:00:00+00:00",
            "2020-01-01T04:00:00+00:00",
        ],
        "temperature": [0, 0.5, 1, 0.5, 0],
        "humidity": [0, 0.5, 1, 0.5, 0],
        "wind_speed": [0, 0.5, 1, 0.5, 0],
        "cloud_cover": [0, 0.5, 1, 0.5, 0],
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

    @pytest.mark.parametrize(
        "start", [dt.datetime(2020, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc), None]
    )
    @pytest.mark.parametrize(
        "end", [dt.datetime(2020, 1, 1, 2, 59, 0, tzinfo=dt.timezone.utc), None]
    )
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
        if not start and not end:
            start_end = None
        else:
            start_end = {}
            start_end.update({"start": start.isoformat()}) if start else None
            start_end.update({"end": end.isoformat()}) if end else None

        # build conditional URL
        url = f"/{self.fc_type}/{plant_name}/{interval}{'/' +
              self.weather_source if self.weather_source else ''}"

        # send request
        response = client.post(url, json=start_end) if start_end else client.post(url)

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
