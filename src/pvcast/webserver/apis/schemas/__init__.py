"""Import all schemas from this module."""


from __future__ import annotations

from jsonschema import ValidationError, validate

from .forecast_sch import (fc_out_energy_day, fc_out_energy_hour,
                           fc_out_energy_ptu, fc_out_power_hour,
                           fc_out_power_ptu)
