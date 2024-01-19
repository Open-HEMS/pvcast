"""Test webserver helper functions."""


import polars as pl
import pytest
from pvlib.location import Location

from pvcast.model.model import PVSystemManager
from pvcast.webserver.models.base import Interval
from pvcast.webserver.routers.helpers import get_forecast_result_dict
from tests.const import LOC_EUW


class TestWebserverHelpers:
    """Test webserver helper functions."""

    @pytest.mark.parametrize("location", [LOC_EUW], indirect=True)
    @pytest.mark.parametrize("fc_type", ["clearsky", "live", "historical"])
    def test_get_forecast_result_dict(
        self,
        pv_sys_mngr: PVSystemManager,
        weather_df: pl.DataFrame,
        fc_type: str,
        location: Location,  # noqa: ARG002 needed for indirect fixture
    ) -> None:
        """Test getting the forecast result dict."""
        response_dict = get_forecast_result_dict(
            "South", pv_sys_mngr, fc_type, Interval.H1, weather_df
        )

        # check response
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

    @pytest.mark.parametrize("location", [LOC_EUW], indirect=True)
    def test_get_forecast_result_dict_wrong_fc_type(
        self,
        pv_sys_mngr: PVSystemManager,
        weather_df: pl.DataFrame,
        location: Location,  # noqa: ARG002 needed for indirect fixture
    ) -> None:
        """Test getting the forecast result dict with wrong fc_type."""
        with pytest.raises(AttributeError, match="No forecasting algorithm found"):
            get_forecast_result_dict(
                "South", pv_sys_mngr, "wrong_fc_type", Interval.H1, weather_df
            )

    @pytest.mark.parametrize("location", [LOC_EUW], indirect=True)
    def test_get_forecast_result_dict_wrong_plant_name(
        self,
        pv_sys_mngr: PVSystemManager,
        weather_df: pl.DataFrame,
        location: Location,  # noqa: ARG002 needed for indirect fixture
    ) -> None:
        """Test getting the forecast result dict with wrong plant name."""
        with pytest.raises(KeyError, match="PV plant wrong_plant_name not found."):
            get_forecast_result_dict(
                "wrong_plant_name", pv_sys_mngr, "clearsky", Interval.H1, weather_df
            )

    @pytest.mark.parametrize("location", [LOC_EUW], indirect=True)
    def test_get_forecast_result_dict_pv_plants_list_empty(
        self,
        pv_sys_mngr: PVSystemManager,
        weather_df: pl.DataFrame,
        location: Location,  # noqa: ARG002 needed for indirect fixture
    ) -> None:
        """Test getting the forecast result dict with empty pv_plants list."""
        pv_sys_mngr._pv_plants = {}
        with pytest.raises(ValueError, match="PV plant list is empty."):
            get_forecast_result_dict(
                "South", pv_sys_mngr, "clearsky", Interval.H1, weather_df
            )

    @pytest.mark.parametrize("location", [LOC_EUW], indirect=True)
    def test_get_forecast_result_dict_pv_plants_weather_df_empty(
        self,
        pv_sys_mngr: PVSystemManager,
        location: Location,  # noqa: ARG002 needed for indirect fixture
    ) -> None:
        """Test getting the forecast result dict with empty weather_df."""
        with pytest.raises(ValueError, match="Weather dataframe is empty."):
            get_forecast_result_dict(
                "South", pv_sys_mngr, "clearsky", Interval.H1, pl.DataFrame()
            )
