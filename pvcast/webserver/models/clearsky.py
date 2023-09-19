"""Clearsky data models for the webserver."""
from __future__ import annotations

from enum import Enum

from .base import BaseDataModel, BaseEnergyModel, BasePowerModel


class ClearskyCompModel(str, Enum):
    """Clearsky computation model: ineichen, haurwitz, simplified_solis."""

    INEICHEN = "Ineichen"
    HAURWITZ = "Haurwitz"
    SIMPLIFIED_SOLIS = "SimplifiedSolis"


class ClearskyModel(BaseDataModel):
    """Clearsky base model."""

    clearskymodel: ClearskyCompModel | None = ClearskyCompModel.INEICHEN


class ClearskyPowerModel(ClearskyModel, BasePowerModel):
    """Clearsky power model."""


class ClearskyEnergyModel(ClearskyModel, BaseEnergyModel):
    """Clearsky energy model."""
