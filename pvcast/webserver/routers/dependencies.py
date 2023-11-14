"""Dependencies for the webserver."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd
from pvlib.location import Location

from ...config.configreader import ConfigReader
from ...model.model import PVSystemManager
from ...weather import API_FACTORY
from ...weather.weather import WeatherAPI

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
def get_weather_sources() -> tuple[WeatherAPI, ...]:
    """Get the weather API instances from _config_reader."""
    # all sources of weather data must be listed in the config file
    weather_data_sources = _config_reader.config["general"]["weather"]["sources"]

    max_forecast_days = pd.Timedelta(
        days=int(_config_reader.config["general"]["weather"]["max_forecast_days"])
    )

    # get the location
    latitude = _config_reader.config["general"]["location"]["latitude"]
    longitude = _config_reader.config["general"]["location"]["longitude"]
    altitude = _config_reader.config["general"]["location"]["altitude"]
    location = Location(
        latitude=latitude, longitude=longitude, tz="UTC", altitude=altitude
    )

    # get all weather APIs from the factory
    weather_apis = []
    for source in weather_data_sources:
        # metadata is everything except name and type
        metadata = source.copy()
        source_type = metadata.pop("type")

        # add the weather API to the list
        weather_apis.append(
            API_FACTORY.get_weather_api(
                source_type,
                max_forecast_days=max_forecast_days,
                location=location,
                **metadata,
            )
        )
    return tuple(weather_apis)
