"""Webserver main file for pvcast."""

from __future__ import annotations

import logging

from flask import Flask
from flask_restx import Api
from waitress import serve

from ..config.configreader import ConfigReader
from .const import API_VERSION, PORT, WEBSERVER_URL
from .controllers.clearsky import api as clearsky_api

# from controllers.historic import api as historic_api
# from controllers.forecast import api as forecast_api


_LOGGER = logging.getLogger(__name__)


class WebServer:
    """Main webserver class."""

    config_reader: ConfigReader
    _api: Api
    _app: Flask

    def __init__(self, config_reader: ConfigReader):
        """Init method."""
        _LOGGER.debug("Webserver init method called.")
        self._api = Api(
            title="PVcast API",
            version=API_VERSION,
            description="RESTful API for PV solar energy and power forecasting.",
            license="MIT",
            license_url="https://choosealicense.com/licenses/mit/",
            contact_url="https://github.com/langestefan/pvcast",
        )

        # add the namespaces
        self._api.add_namespace(clearsky_api, path="/forecast")
        # api.add_namespace(historic_api, path="/historic")
        # api.add_namespace(forecast_api, path="/forecast")

        self.config_reader = config_reader
        self._app = Flask(__name__)
        self._api.init_app(self._app)

    def run(self):
        """Initialize and run the webserver."""
        self._app.logger.info("Launching pvcast webserver at: http://%s:%s", WEBSERVER_URL, PORT)

        # get the weather platform config

        serve(self._app, host=WEBSERVER_URL, port=PORT, threads=1)
