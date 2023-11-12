"""Live data models for the webserver."""
from __future__ import annotations

from pydantic import BaseModel
from enum import Enum

from .base import BaseDataModel
from ..routers.dependencies import get_weather_sources


class WeatherSource(BaseModel):
    """Weather source for live forecast."""

    weather_source: str


class LiveModel(BaseDataModel, WeatherSource):
    """Live model."""


# create enum of weather sources configured in config.yaml
weather_sources = {obj.name: obj.name for obj in get_weather_sources()}
TypeEnum = Enum("TypeEnum", weather_sources)


class SourceEnum(str, Enum):
    """Proxy enum."""


WeatherSources = SourceEnum("TypeEnum", weather_sources)
