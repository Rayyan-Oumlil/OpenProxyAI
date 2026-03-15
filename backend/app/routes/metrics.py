"""Prometheus metrics endpoint -- GET /metrics."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter(tags=["Metrics"])


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Expose Prometheus metrics in text format."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
