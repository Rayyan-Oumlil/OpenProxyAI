"""CORS middleware configuration for web-app origins."""

import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings


def _parse_origins(raw: str) -> list[str]:
    """Accept JSON array or comma-separated string."""
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(o) for o in parsed]
    except (json.JSONDecodeError, TypeError):
        pass
    return [o.strip() for o in raw.split(",") if o.strip()]


def add_cors_middleware(app: FastAPI) -> None:
    """Register CORSMiddleware with origins from settings."""
    origins = _parse_origins(settings.CORS_ORIGINS)
    if "*" in origins:
        # Wildcard CORS requires allow_credentials=False (CORS spec).
        # For credentialed requests (cookies/auth), set explicit origins instead.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
