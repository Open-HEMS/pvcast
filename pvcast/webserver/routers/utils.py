"""Utilities for the webserver."""
from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/list_endpoints/")
def list_endpoints(request: Request) -> list[dict[str, str]]:
    """List all endpoints.

    :param request: The request
    """
    return [{"path": route.path, "name": route.name} for route in request.app.routes]
