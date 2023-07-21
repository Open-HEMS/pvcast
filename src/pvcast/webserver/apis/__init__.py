from __future__ import annotations

from flask_restx import Api

from .forecast import api as forecast_api
from .historic import api as historic_api

# create the API object
api = Api(
    title="PVcast API",
    version="1.0",
    description="RESTful API for PV solar energy and power forecasting.",
    license="MIT",
    license_url="https://choosealicense.com/licenses/mit/",
    contact_url="https://github.com/langestefan/pvcast",
)

# add the namespaces
api.add_namespace(forecast_api, path="/forecast")
api.add_namespace(historic_api, path="/historic")
