"""Weather API module."""
from __future__ import annotations

from .clearoutside import WeatherAPIClearOutside
from .hass import WeatherAPIHASS
from .weather import WeatherAPIFactory

API_FACTORY = WeatherAPIFactory()
API_FACTORY.register("clearoutside", WeatherAPIClearOutside)
API_FACTORY.register("hass", WeatherAPIHASS)
