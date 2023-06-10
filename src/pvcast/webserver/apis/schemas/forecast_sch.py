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
energy_freqs = ["ptu", "hour", "day"]
fc_out_energy = {freq: deepcopy(_fc_out) for freq in energy_freqs}
for freq in energy_freqs:
    fc_out_energy[freq]["properties"]["unit"]["enum"] = ["Wh", "kWh"]
    fc_out_energy[freq]["properties"]["frequency"]["enum"] = [freq]

# power forecasts
power_freqs = ["ptu", "hour"]
fc_out_power = {freq: deepcopy(_fc_out) for freq in power_freqs}
for freq in power_freqs:
    fc_out_power[freq]["properties"]["unit"]["enum"] = ["W", "kW"]
    fc_out_power[freq]["properties"]["frequency"]["enum"] = [freq]
