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

from flask_restx import Namespace, Resource, SchemaModel

# define the API namespace
api = Namespace("forecast", "Short-term PV power and energy forecast data.")


# # define the model and add it to the API
# fc_model = SchemaModel("Forecast", fc_schema)
# api.models[fc_model.name] = fc_model


# @api.route("/updateweather", methods=["POST"])
# class UpdateWeather(Resource):
#     @api.doc(description="Force update the weather forecast data.")
#     def post(self):
#         return {}


# @api.route("/power/ptu/<name>", methods=["GET"])
# class ForecastPowerPTU(Resource):
#     @api.doc(model=fc_model.name)
#     def get(self, name):
#         return {}


# @api.route("/power/hour/<name>", methods=["GET"])
# class ForecastPowerHour(Resource):
#     @api.doc(model=fc_model.name)
#     def get(self, name):
#         return {}


# @api.route("/energy/ptu/<name>", methods=["GET"])
# class ForecastEnergyPTU(Resource):
#     @api.doc(model=fc_model.name)
#     def get(self, name):
#         return {}


# @api.route("/energy/hour/<name>", methods=["GET"])
# class ForecastEnergyHour(Resource):
#     @api.doc(model=fc_model.name)
#     def get(self, name):
#         return {}
