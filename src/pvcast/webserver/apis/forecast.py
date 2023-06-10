""" Forecast API endpoints.

These endpoints return the forecasted power output or energy output of all PV systems in the
YAML configuration file, reported as a list. The power forecast uses a weather forecast from any configured input source.
All calls to the forecast endpoints will return a forecast for a horizon of [1,8] days, depending on the horizon of the
weather data source. The energy forecast is calculated by integrating the power forecast over the forecast horizon.
One PTU = 15 min. Power Transfer Unit. All endpoints accept a maximum look-ahead {date} parameter in the format YYYY-MM-DD.
Forecasts are computed for timepoints up to and including the look-ahead date. If no look-ahead date is given, the
forecast is computed for all available weather forecast data. The following endpoints are available:

    - /forecast/power/ptu/<name>: Get the forecasted power output in watts at 15 minute intervals
    - /forecast/power/hour/<name>: Get the forecasted power output in watts at hourly intervals.
    - /forecast/energy/ptu/<name>: Get the forecasted energy output in kWh at 15 minute intervals.
    - /forecast/energy/hour/<name>: Get the forecasted energy output in kWh at hourly intervals.
    - /forecast/energy/day/<name>: Get the forecasted energy output in kWh at daily intervals.
    - /forecast/updateweather: Async way to force update the weather forecast data.
"""
from __future__ import annotations

import logging

from flask_restx import Namespace, Resource, SchemaModel

from .schemas import fc_out_energy, fc_out_power

_LOGGER = logging.getLogger(__name__)

# define the API namespace
api = Namespace("forecast", "Short-term PV power and energy forecast data.")


# define the models and add them to the API
energy_models = {}
power_models = {}

# create energy and power models for each schema
for name, schema in fc_out_energy.items():
    energy_model = SchemaModel(name, schema)
    energy_models[name] = energy_model
    api.models[energy_model.name] = energy_model

for name, schema in fc_out_power.items():
    power_model = SchemaModel(name, schema)
    power_models[name] = power_model
    api.models[power_model.name] = power_model


@api.route("/updateweather", methods=["POST"])
class UpdateWeather(Resource):
    @api.doc(description="Force update the weather forecast data.")
    def post(self):
        """Force update the weather forecast data."""
        return {}


@api.route("/power/ptu/<name>", methods=["GET"])
class ForecastPowerPTU(Resource):
    @api.doc(model=power_models["ptu"])
    def get(self, name):
        """Forecasted power output in Watts at 15 minute intervals."""
        return {}


@api.route("/power/hour/<name>", methods=["GET"])
class ForecastPowerHour(Resource):
    @api.doc(model=power_models["hour"])
    def get(self, name):
        """Forecasted power output in Watts at hourly intervals."""
        return {}


@api.route("/energy/ptu/<name>", methods=["GET"])
class ForecastEnergyPTU(Resource):
    @api.doc(model=energy_models["ptu"])
    def get(self, name):
        """Forecasted energy output in kWh at 15 minute intervals."""
        return {}


@api.route("/energy/hour/<name>", methods=["GET"])
class ForecastEnergyHour(Resource):
    @api.doc(model=energy_models["hour"])
    def get(self, name):
        """Forecasted energy output in kWh at hourly intervals."""
        return {}
