"""Clearsky data models for the webserver."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from .base import BaseDataModel


class ClearskyCompModel(str, Enum):
    """Clearsky computation model: ineichen, haurwitz, simplified_solis."""

    INEICHEN = "Ineichen"
    HAURWITZ = "Haurwitz"
    SIMPLIFIED_SOLIS = "SimplifiedSolis"


class ClearskyComp(BaseModel):
    """Clearsky computation model."""

    clearskymodel: ClearskyCompModel = ClearskyCompModel.INEICHEN


class ClearskyModel(BaseDataModel, ClearskyComp):
    """Clearsky model."""
