"""Test the weather module."""
from __future__ import annotations

import pytest
from jsonschema import ValidationError, validate

from pvcast.webserver.apis.schemas import fc_out_energy, fc_out_power


class TestWebServer:
    """Test webserver."""

    @pytest.fixture(params=fc_out_power.keys())
    def forecast_power_data(self, request):
        """Return a forecast power data structure."""
        return {
            "name": "mypvsystem",
            "unit": "W",
            "frequency": request.param,
            "data": [
                {
                    "date": "2020-01-01T00:00:00",
                    "value": 24.6,
                }
            ],
        }

    @pytest.fixture(params=fc_out_energy.keys())
    def forecast_energy_data(self, request):
        """Return a forecast energy data structure."""
        return {
            "name": "mypvsystem",
            "unit": "Wh",
            "frequency": request.param,
            "data": [
                {
                    "date": "2020-01-01T00:00:00",
                    "value": 13.1,
                }
            ],
        }

    def test_fc_out_power_invalid(self, forecast_power_data):
        """Validate forecast power data schemes."""
        forecast_power_data["unit"] = "invalid"
        schema = fc_out_power[forecast_power_data["frequency"]]
        with pytest.raises(ValidationError):
            validate(instance=forecast_power_data, schema=schema)

    def test_fc_out_power(self, forecast_power_data):
        """Validate forecast power data schemes."""
        schema = fc_out_power[forecast_power_data["frequency"]]
        validate(instance=forecast_power_data, schema=schema)

    def test_fc_out_energy(self, forecast_energy_data):
        """Validate forecast energy data schemes."""
        schema = fc_out_energy[forecast_energy_data["frequency"]]
        validate(instance=forecast_energy_data, schema=schema)
