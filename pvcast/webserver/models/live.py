"""Live data models for the webserver."""
from __future__ import annotations

from pydantic import BaseModel

from .base import BaseDataModel


class WeatherSource(BaseModel):
    """Weather source for live forecast."""

    weather_source: str


class LiveModel(BaseDataModel, WeatherSource):
    """Live model."""
