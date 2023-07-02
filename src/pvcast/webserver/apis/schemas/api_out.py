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
# for timeseries frequency options see: https://pandas.pydata.org/docs/user_guide/timeseries.html#offset-aliases
energy_sch = Schema(
    base_sch.extend(
        {
            Required("unit"): In(["Wh", "kWh"]),
            Required("frequency"): In(["15Min", "30Min", "1H", "1D", "1W", "M", "Y"]),
            Required("data"): [
                {
                    # HA uses RFC 3339 timestamps in format: "2023-07-01T21:00:00+00:00"
                    Required("datetime"): All(str, Datetime(format="%Y-%m-%dT%H:%M:%S+00:00")),
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
            Required("frequency"): In(["15Min", "30Min", "1H"]),
            Required("data"): [
                {
                    # HA uses RFC 3339 timestamps in format: "2023-07-01T21:00:00+00:00"
                    Required("datetime"): All(str, Datetime(format="%Y-%m-%dT%H:%M:%S+00:00")),
                    Required("value"): All(float, Range(min=0)),
                }
            ],
        }
    )
)
