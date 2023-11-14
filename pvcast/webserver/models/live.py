"""Live data models for the webserver."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from ..routers.dependencies import get_weather_sources
from .base import BaseDataModel


class WeatherSource(BaseModel):
    """Weather source for live forecast."""

    weather_source: str


class LiveModel(BaseDataModel, WeatherSource):
    """Live model."""


# create enum of weather sources configured in config.yaml
weather_sources = {obj.name: obj.name for obj in get_weather_sources()}
TypeEnum = Enum("TypeEnum", weather_sources)  # type: ignore[misc]


class SourceEnum(str, Enum):
    """Proxy enum."""


WeatherSources = SourceEnum("TypeEnum", weather_sources)  # type: ignore[call-overload]
