"""Main module for the webserver."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import HTMLResponse  # noqa: TCH002

from .const import API_VERSION
from .routers.clearsky import router as clearsky_router
from .routers.historical import router as historical_router
from .routers.live import router as live_router
from .routers.utils import router as utils_router

STATIC_PATH = Path(__file__).parent / "static"

app = FastAPI(
    title="PV Cast",
    description="A webserver for the PV Cast project.",
    version=API_VERSION,
    docs_url=None,
    redoc_url=None,
)

app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")

# add core function routers
app.include_router(clearsky_router, prefix="/clearsky", tags=["clearsky"])
app.include_router(historical_router, prefix="/historical", tags=["historical"])
app.include_router(live_router, prefix="/live", tags=["live"])
app.include_router(utils_router, prefix="/utils", tags=["utilities"])

# if env variable SOLARA_APP is set, enable and import solara
if os.environ.get("SOLARA_APP"):
    import solara.server.fastapi

    app.mount("/solara", app=solara.server.fastapi.app)


@app.get("/docs", include_in_schema=False)
def overridden_swagger() -> HTMLResponse:
    """Override the default swagger page to add a favicon.

    :return: The swagger page.
    """
    return get_swagger_ui_html(
        openapi_url="/openapi.json", title="PV Cast", swagger_favicon_url="/favicon"
    )


@app.get("/favicon", include_in_schema=False)
async def favicon() -> FileResponse:
    """Get the favicon. Favicon attribution: gungyoga04."""
    return FileResponse(STATIC_PATH / "favicon.png")
