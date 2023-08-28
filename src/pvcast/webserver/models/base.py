"""Base data model with common fields for pvcast API."""
from __future__ import annotations

from flask_restx import Model, fields

# base model with common response fields
base_model = Model(
    "BaseModel",
    {
        "plant_name": fields.String(
            required=True,
            description="Name of the PV plant",
            example="My PV plant",
        ),
        "timezone": fields.String(
            required=True,
            description="Timezone of the returned data",
            example="Europe/Berlin",
        ),
        "interval": fields.String(
            required=True,
            description="Interval of the returned data",
            example="1H",
        ),
        "result": fields.Raw(
            required=True,
            description="Result data",
            example={
                "2022-10-12 07:00:00": 0,
                "2022-10-12 08:00:00": 1570,
            },
        ),
    },
)

# base model with common response fields for power data
base_model_power = base_model.clone(
    "BaseModelPower",
    {"unit": fields.String(default="W", required=True, description="Estimated PV power output in Watts")},
)

# base model with common response fields for energy data
base_model_energy = base_model.clone(
    "BaseModelEnergy",
    {"unit": fields.String(default="Wh", required=True, description="Estimated PV energy output in Wh")},
)

__all__ = ["base_model_power", "base_model_energy"]
