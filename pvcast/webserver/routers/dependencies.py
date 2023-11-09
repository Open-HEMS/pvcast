"""Dependencies for the webserver."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd
from pvlib.location import Location

from ...config.configreader import ConfigReader
from ...model.model import PVSystemManager
from ...weather import API_FACTORY

# create a singleton config reader
_config_path = Path("config.yaml")
_secrets_path = Path("secrets.yaml")
_config_reader = ConfigReader(_config_path, _secrets_path)


@lru_cache
def get_pv_system_mngr() -> PVSystemManager:
    """Get the PV system manager instance."""
    return PVSystemManager(
        config=_config_reader.config["plant"],
        lat=_config_reader.config["general"]["location"]["latitude"],
        lon=_config_reader.config["general"]["location"]["longitude"],
        alt=_config_reader.config["general"]["location"]["altitude"],
    )


@lru_cache
def get_weather_api() -> API_FACTORY:
    """Get the weather API instance from _config_reader."""
    # metadata are all keys at level "source" which are not "source"
    metadata: dict = _config_reader.config["general"]["weather"]["weather_source"]
    weather_data_source = metadata.pop("source")
    max_forecast_days = pd.Timedelta(
        days=int(_config_reader.config["general"]["weather"]["max_forecast_days"])
    )
    latitude = _config_reader.config["general"]["location"]["latitude"]
    longitude = _config_reader.config["general"]["location"]["longitude"]
    altitude = _config_reader.config["general"]["location"]["altitude"]
    location = Location(
        latitude=latitude, longitude=longitude, tz="UTC", altitude=altitude
    )
    return API_FACTORY.get_weather_api(
        weather_data_source,
        max_forecast_days=max_forecast_days,
        location=location,
        **metadata,
    )


__all__ = ["get_pv_system_mngr"]
