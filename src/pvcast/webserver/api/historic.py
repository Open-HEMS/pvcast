from __future__ import annotations

from flask_restx import Namespace, Resource

api = Namespace("historic", "Expected PV energy and power based on historic PVGIS TMY data.")


@api.route("/")
class Myclass(Resource):
    def get(self):
        return {}
