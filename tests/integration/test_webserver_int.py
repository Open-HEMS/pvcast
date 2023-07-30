"""Test the weather module."""
from __future__ import annotations

import pytest
import voluptuous as vol

from pvcast.webserver.apis.schemas.api_out import energy_sch, power_sch


class TestWebServer:
    """Test webserver."""

    @pytest.fixture(params=["15Min", "30Min", "1H"])
    def forecast_power_data(self, request):
        """Return a forecast power data structure."""
        return {
            "plantname": "mypvsystem1",
            "unit": "W",
            "frequency": request.param,
            "data": [
                {
                    "datetime": "2023-07-01T21:00:00+00:00",
                    "value": 24.6,
                }
            ],
        }

    @pytest.fixture(params=["15Min", "30Min", "1H", "1D", "1W", "M", "Y"])
    def forecast_energy_data(self, request):
        """Return a forecast energy data structure."""
        return {
            "plantname": "mypvsystem2",
            "unit": "Wh",
            "frequency": request.param,
            "data": [
                {
                    "datetime": "2023-07-01T21:00:00+00:00",
                    "value": 13.1,
                }
            ],
        }

    def test_fc_out_power_invalid(self, forecast_power_data):
        """Validate forecast power data schemes."""
        forecast_power_data["unit"] = "invalid"
        schema = power_sch
        with pytest.raises(vol.Invalid):
            schema(forecast_power_data)

    def test_fc_out_power(self, forecast_power_data):
        """Validate forecast power data schemes."""
        schema = power_sch
        schema(forecast_power_data)

    def test_fc_out_energy(self, forecast_energy_data):
        """Validate forecast energy data schemes."""
        schema = energy_sch
        schema(forecast_energy_data)
