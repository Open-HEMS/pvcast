"""Main module for the webserver."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.responses import FileResponse

from .const import API_VERSION
from .routers.clearsky import router as clearsky_router
from .routers.historical import router as historical_router
from .routers.live import router as live_router

_LOGGER = logging.getLogger("uvicorn")
FAV_ICON_PATH = "pvcast/webserver/favicon.png"

app = FastAPI(
    title="PV Cast",
    description="A webserver for the PV Cast project.",
    version=API_VERSION,
    docs_url="/",
    redoc_url=None,
)

app.include_router(clearsky_router, prefix="/clearsky", tags=["clearsky"])
app.include_router(historical_router, prefix="/historical", tags=["historical"])
app.include_router(live_router, prefix="/live", tags=["live"])


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> FileResponse:
    """Get the favicon."""
    _LOGGER.info("Getting favicon")
    return FileResponse(FAV_ICON_PATH)
