from __future__ import annotations

from .clearoutside import WeatherAPIClearOutside
from .weather import WeatherAPIFactory

API_FACTORY = WeatherAPIFactory()
API_FACTORY.register("clearoutside", WeatherAPIClearOutside)
