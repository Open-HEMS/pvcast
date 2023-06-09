"""Test the weather module."""
from __future__ import annotations

import pytest
from jsonschema import ValidationError, validate

from pvcast.webserver.apis.schemas import (fc_out_energy_day,
                                           fc_out_energy_hour,
                                           fc_out_energy_ptu,
                                           fc_out_power_hour, fc_out_power_ptu)


class TestWebServer:
    """Test webserver."""

    energy_test_dict = {
        "ptu": fc_out_energy_ptu,
        "hour": fc_out_energy_hour,
        "day": fc_out_energy_day,
    }
    power_test_dict = {
        "ptu": fc_out_power_ptu,
        "hour": fc_out_power_hour,
    }

    @pytest.fixture(params=power_test_dict.keys())
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

    @pytest.fixture(params=energy_test_dict.keys())
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

    def test_fc_out_power(self, forecast_power_data):
        """Validate forecast power data schemes."""
        schema = self.power_test_dict[forecast_power_data["frequency"]]
        validate(instance=forecast_power_data, schema=schema)

    def test_fc_out_energy(self, forecast_energy_data):
        """Validate forecast energy data schemes."""
        schema = self.energy_test_dict[forecast_energy_data["frequency"]]
        validate(instance=forecast_energy_data, schema=schema)
