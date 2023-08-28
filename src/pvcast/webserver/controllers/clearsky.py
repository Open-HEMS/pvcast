""" Clearsky API controller.

It offers the following endpoints:

- /clearsky/energy/<name>/<interval>
Returns the most recently estimated PV energy output in Wh at the given interval <interval> for the given PV system
<name>.

POST: This will force a recalculation of the energy output using the latest available weather data,
which may take some time.

GET: Will return 404 if no data is available. This should be used as a fast, cached alternative of the POST method.

- /clearsky/power/<name>/<interval>
Returns the estimated PV power output in Watts at the given interval <interval> for the given PV system <name>.
POST

"""
from __future__ import annotations

from flask_restx import Namespace, Resource

from ..models.clearsky import clearsky_energy_model, clearsky_power_model

api = Namespace("clearsky", "Estimated PV output based on clearsky model")
api.models[clearsky_energy_model.name] = clearsky_energy_model
api.models[clearsky_power_model.name] = clearsky_power_model


# base model with common fields
class BaseClearSkyModel(Resource):
    """Base model for Clearsky API."""

    name: str
    interval: str


# model for clearsky power
@api.route("/power/<name>/<interval>", methods=["GET", "POST"])
class ClearSkyPowerModel(BaseClearSkyModel):
    """Model for Clearsky power API."""

    name: str
    interval: str
    power: float

    @api.doc(
        responses={
            200: "Success",
            404: "No data available",
        }
    )
    @api.marshal_with(clearsky_power_model)
    def get(self, name: str, interval: str = "1H"):
        """Get the estimated PV power output in Watts at the given interval <interval> for the given PV system <name>.

        GET: Will return 404 if no data is available. This should be used as a fast, cached alternative of the POST\
        method.

        :param name: Name of the PV system
        :param interval: Interval of the returned data
        :return: Estimated PV power output in Watts at the given interval <interval> for the given PV system <name>
        """
        return {}

    @api.doc(
        responses={
            200: "Success",
            404: "No data available",
        }
    )
    @api.marshal_with(clearsky_power_model)
    def post(self, name: str, interval: str = "1H"):
        """Get the estimated PV power output in Watts at the given interval <interval> for the given PV system <name>.

        POST: This will force a recalculation of the power output using the latest available weather data,\
        which may take some time.

        :param name: Name of the PV system
        :param interval: Interval of the returned data
        :return: Estimated PV power output in Watts at the given interval <interval> for the given PV system <name>
        """
        return {}


# model for clearsky energy
@api.route("/energy/<name>/<interval>", methods=["GET", "POST"])
class ClearSkyEnergyModel(BaseClearSkyModel):
    """Model for Clearsky energy API."""

    name: str
    interval: str
    energy: float

    @api.doc(
        responses={
            200: "Success",
            404: "No data available",
        }
    )
    @api.marshal_with(clearsky_energy_model)
    def get(self, name: str, interval: str = "1H"):
        """Get the most recently estimated PV energy output in Wh at the given interval <interval> for the given PV\
        system <name>.

        GET: Will return 404 if no data is available. This should be used as a fast, cached alternative of the POST\
        method.

        :param name: Name of the PV system
        :param interval: Interval of the returned data
        :return: Most recently estimated PV energy output in Wh at the given interval <interval> for the given PV
        system <name>
        """
        return {}

    @api.doc(
        responses={
            200: "Success",
            404: "No data available",
        }
    )
    @api.marshal_with(clearsky_energy_model)
    def post(self, name: str, interval: str = "1H"):
        """Get the most recently estimated PV energy output in Wh at the given interval <interval> for the given PV\
        system <name>.

        POST: This will force a recalculation of the energy output using the latest available weather data,\
        which may take some time.

        :param name: Name of the PV system
        :param interval: Interval of the returned data
        :return: Most recently estimated PV energy output in Wh at the given interval <interval> for the given PV\
        system <name>
        """
        return {}
