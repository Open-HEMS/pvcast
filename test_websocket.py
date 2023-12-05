#!/usr/bin/env python

import json

from websockets.sync.client import connect


def hello():
    with connect("ws://192.168.1.217:8123/api/websocket") as websocket:
        message = websocket.recv()
        print(f"Received: {message}")

        # send auth message
        websocket.send(
            json.dumps(
                {
                    "type": "auth",
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJhMTI1Mzg4MTVlZDk0MzRmODQ0YjJmMGIzZDc1MGVmOSIsImlhdCI6MTcwMTQ0MjQwNywiZXhwIjoyMDE2ODAyNDA3fQ.KkHCfCuFdkUyPb3LNA8HcEvIH2IQ1rmtSDn3haGbKeM",
                }
            )
        )
        message = websocket.recv()
        print(f"Received: {message}")

        # send get weather forecast message
        get_weather_fc = {
            "id": 24,
            "type": "weather/subscribe_forecast",
            "entity_id": "weather.forecast_thuis",
            "forecast_type": "hourly",
        }

        websocket.send(json.dumps(get_weather_fc))
        message = websocket.recv()
        print(f"Received: {message}")
        message = websocket.recv()
        print(f"Received: {message}")


hello()
