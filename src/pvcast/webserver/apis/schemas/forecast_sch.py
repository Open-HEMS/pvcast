"""Forecast schemas for the webserver API."""
from __future__ import annotations

from copy import deepcopy

# forecast base schema
_fc_out = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "unit": {"type": "string", "enum": ["W", "kW", "Wh", "kWh"]},
        "frequency": {"type": "string", "enum": ["ptu, hour, day"]},
        "data": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "format": "date-time", "example": "2020-01-01T00:00:00"},
                    "value": {"type": "number", "minimum": 0, "example": 4.52},
                },
                "required": ["date", "value"],
            },
        },
    },
    "required": ["name", "unit", "data", "frequency"],
}

# energy forecasts
_fc_out_energy = deepcopy(_fc_out)
_fc_out_energy["properties"]["unit"]["enum"] = ["Wh", "kWh"]

fc_out_energy_ptu = deepcopy(_fc_out_energy)
fc_out_energy_ptu["properties"]["frequency"]["enum"] = ["ptu"]

fc_out_energy_hour = deepcopy(_fc_out_energy)
fc_out_energy_hour["properties"]["frequency"]["enum"] = ["hour"]

fc_out_energy_day = deepcopy(_fc_out_energy)
fc_out_energy_day["properties"]["frequency"]["enum"] = ["day"]

# power forecasts
_fc_out_power = deepcopy(_fc_out)
_fc_out_power["properties"]["unit"]["enum"] = ["W", "kW"]

fc_out_power_ptu = deepcopy(_fc_out_power)
fc_out_power_ptu["properties"]["frequency"]["enum"] = ["ptu"]

fc_out_power_hour = deepcopy(_fc_out_power)
fc_out_power_hour["properties"]["frequency"]["enum"] = ["hour"]
