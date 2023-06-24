"""Forecast schemas for the webserver API."""
from __future__ import annotations

from voluptuous import All, Datetime, In, Range, Required, Schema

# forecast base schema
base_sch = Schema(
    {
        Required("plantname"): str,
    }
)

# energy forecast schemas
energy_sch = Schema(
    base_sch.extend(
        {
            Required("unit"): In(["Wh", "kWh"]),
            Required("frequency"): In(["15min", "30min", "hour", "day", "week", "month", "year"]),
            Required("data"): [
                {
                    Required("datetime"): All(str, Datetime(format="%Y-%m-%dT%H:%M")),
                    Required("value"): All(float, Range(min=0)),
                }
            ],
        }
    )
)

# power forecast schemas
power_sch = Schema(
    base_sch.extend(
        {
            Required("unit"): In(["W", "kW"]),
            Required("frequency"): In(["15min", "30min", "hour"]),
            Required("data"): [
                {
                    Required("datetime"): All(str, Datetime(format="%Y-%m-%dT%H:%M")),
                    Required("value"): All(float, Range(min=0)),
                }
            ],
        }
    )
)
