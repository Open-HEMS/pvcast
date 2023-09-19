"""Main module for the webserver."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.responses import FileResponse

from .const import API_VERSION
from .routers.clearsky import router as clearsky_router

_LOGGER = logging.getLogger("uvicorn")


app = FastAPI(
    title="PV Cast",
    description="A webserver for the PV Cast project.",
    version=API_VERSION,
)

app.include_router(clearsky_router, prefix="/clearsky", tags=["clearsky"])

favicon_path = "pvcast/webserver/favicon.png"


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Get the favicon."""
    _LOGGER.info("Getting favicon")
    return FileResponse(favicon_path)
