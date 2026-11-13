"""Prometheus metrics endpoint -- GET /metrics."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.config import settings

router = APIRouter(tags=["Metrics"])


@router.get("/metrics", include_in_schema=False)
async def metrics(authorization: str | None = Header(default=None)) -> Response:
    """Expose Prometheus metrics in text format; with METRICS_BEARER_TOKEN set, only to a caller that sends it."""
    expected = settings.METRICS_BEARER_TOKEN
    if expected:
        scheme, _, presented = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(presented.strip().encode(), expected.encode()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
                headers={"WWW-Authenticate": "Bearer"},
            )
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
