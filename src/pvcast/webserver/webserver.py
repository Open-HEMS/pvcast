"""
Webserver based on Flask that serves a few endpoints for the PVcast app.
Multi-resolution, multi-horizon distributed solar PV power forecasting.

Endpoints:
  - PV forecast endpoints. These endpoints return the forecasted power output or energy output of all PV systems in the
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

  - PV historic endpoints. These endpoints return expected energy based on 20 year average historic PVGIS data.
    TMY data is used for the historic energy endpoints. TMY is a typical meteorological year, which is a dataset of
    hourly values of solar radiation and meteorological elements for a 1 year period averaged over many years. See
    also: https://joint-research-centre.ec.europa.eu/pvgis-online-tool/pvgis-tools/pvgis-typical-meteorological-year-tmy-generator_en.
    The following endpoints are available:

        - /historic/energy/day/<name>: Get the expected energy output in kWh at daily intervals for a month of TMY data.
        - /historic/energy/month/<name>: Get the expected energy output in kWh at monthly intervals for a year of TMY data.

    The tag <name> is the name of the PV system as defined in the YAML configuration file (plant: name: <name>).
    The <name> tage is case insensitive. The endpoints return a JSON object with the following structure:

        {
            "name": <name>,
            "unit": <unit>,
            "data": [
                {
                    "date": <date>,
                    "value": <value>
                },
                ...
            ]
        }

    The date is a string in the format YYYY-MM-DD HH:MM for monthly, daily, hourly and 15 minute data. The value is a
    float. The unit is a string with the unit of the value, e.g. kWh. The data is a list of dictionaries with the
    date, value and unit keys.

    Tips:
      - Use @etag to cache the response

"""

from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify
from flask_restx import Api
from waitress import serve

from ..config.configreader import ConfigReader
from .apis import api

app = Flask(__name__)
api.init_app(app)

# webserver configuration
port = 5000
web_ui_url = "0.0.0.0"

# global configuration
config_reader = None


def run(config_path: Path, secrets_path: Path):
    """Initialize and run the webserver.

    :param config_path: Path to the configuration yaml file.
    :param secrets_path: Path to the secrets yaml file.
    """

    # read the configuration
    global config_reader
    config_reader = ConfigReader(config_path, secrets_path)

    # start server
    app.logger.info("Launching pvcast webserver at: http://" + web_ui_url + ":" + str(port))
    serve(app, host=web_ui_url, port=port, threads=2)
