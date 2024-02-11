"""Dependencies for the webserver."""
from __future__ import annotations

import datetime as dt
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from pvlib.location import Location

from pvcast.config.configreader import ConfigReader
from pvcast.model.model import PVSystemManager
from pvcast.weather import API_FACTORY

if TYPE_CHECKING:
    from pvcast.weather.weather import WeatherAPI


_LOGGER = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_config_reader() -> ConfigReader:
    """Get the config reader instance."""
    _LOGGER.debug("Creating new ConfigReader instance.")
    config_path = os.environ.get("CONFIG_FILE_PATH")
    secrets_path = os.environ.get("SECRETS_FILE_PATH")
    _LOGGER.info("Reading config file: %s", config_path)
    return ConfigReader(Path(config_path), Path(secrets_path) if secrets_path else None)  # type: ignore[arg-type]


@lru_cache(maxsize=1)
def get_pv_system_mngr() -> PVSystemManager:
    """Get the PV system manager instance."""
    _LOGGER.debug("Creating new PVSystemManager instance.")
    config_reader = get_config_reader()
    return PVSystemManager(
        config=config_reader.config["plant"],  # type: ignore[arg-type]
        lat=config_reader.config["general"]["location"]["latitude"],  # type: ignore[index]
        lon=config_reader.config["general"]["location"]["longitude"],  # type: ignore[index]
        alt=config_reader.config["general"]["location"]["altitude"],  # type: ignore[index]
    )


@lru_cache(maxsize=1)
def get_weather_sources() -> tuple[WeatherAPI, ...]:
    """Get the weather API instances from config_reader."""
    _LOGGER.debug("Creating new WeatherAPI instances.")
    config_reader = get_config_reader()

    # all sources of weather data must be listed in the config file
    weather_data_sources = config_reader.config["general"]["weather"]["sources"]  # type: ignore[index]

    max_forecast_days = dt.timedelta(
        days=int(config_reader.config["general"]["weather"]["max_forecast_days"])  # type: ignore[index]
    )

    # get the location
    latitude = config_reader.config["general"]["location"]["latitude"]  # type: ignore[index]
    longitude = config_reader.config["general"]["location"]["longitude"]  # type: ignore[index]
    altitude = config_reader.config["general"]["location"]["altitude"]  # type: ignore[index]
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
