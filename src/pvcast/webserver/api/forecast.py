""" Forecast API endpoints.

These endpoints return the forecasted power output or energy output of all PV systems in the
YAML configuration file, reported as a list. The power forecast uses a weather forecast from any configured input
source. All calls to the forecast endpoints will return a forecast for a horizon of [1,8] days, depending on the horizon
of the weather data source. The energy forecast is calculated by integrating the power forecast over the forecast
horizon. One PTU = 15 min. Power Transfer Unit. All endpoints accept a maximum look-ahead {date} parameter in the format
YYYY-MM-DD. Forecasts are computed for timepoints up to and including the look-ahead date. If no look-ahead date is
given, the forecast is computed for all available weather forecast data. The following endpoints are available:

    - /forecast/power/<frequency>/<name>: Forecasted power output at <frequency> frequency for PV plant <name>.
    - /forecast/energy/<frequency>/<name>: Forecasted energyat <frequency> frequency for PV plant <name>.
    - /forecast/updateweather: Async way to force update the weather forecast data.
"""
from __future__ import annotations

import logging

from flask_restx import Namespace, Resource, SchemaModel

from .schemas.api_out import energy_sch, power_sch

_LOGGER = logging.getLogger(__name__)

# define the API namespace
api = Namespace("forecast", "Short-term PV power and energy forecast data.")

# schemas
energy_model = SchemaModel("Energy", energy_sch)
api.models[energy_model.name] = energy_model

power_model = SchemaModel("Power", power_sch)
api.models[power_model.name] = power_model


@api.route("/updateweather", methods=["POST"])
class UpdateWeather(Resource):
    """Async way to force update the weather forecast data."""

    @api.doc(description="Force update the weather forecast data.")
    def post(self):
        """Force update the weather forecast data."""
        return {}


@api.route("/power/<frequency>/<plantname>", methods=["GET"])
class ForecastPower(Resource):
    """Forecasted power resource."""

    @api.doc(model=power_model)
    def get(self, frequency: str, plantname: str):
        """Forecasted power output in kWh at <frequency> frequency for PV plant <name>."""
        return {}


@api.route("/energy/<frequency>/<plantname>", methods=["GET"])
class ForecastEnergy(Resource):
    """Forecasted energy resource."""

    @api.doc(model=energy_model)
    def get(self, frequency: str, plantname: str):
        """Forecasted energy output in Wh at <frequency> frequency for PV plant <name>."""
        return {}
