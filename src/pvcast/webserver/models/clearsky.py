"""Clearsky schema models."""
from __future__ import annotations

from flask_restx import fields

from .base import base_model_energy, base_model_power

comp_model_cs = {
    "clearsky_model": fields.String(
        required=True,
        description="Name of the computational clearsky model used to estimate the PV power output",
        example="ineichen",
    ),
}

# model for clearsky power
clearsky_power_model = base_model_power.clone("ClearSkyPowerModel", comp_model_cs)

# model for clearsky energy
clearsky_energy_model = base_model_energy.clone("ClearSkyEnergyModel", comp_model_cs)
