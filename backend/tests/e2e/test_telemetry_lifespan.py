"""Telemetry wiring through the real application lifespan (own module: it starts and stops the whole app).

Kept apart from the other e2e tests because each module shares one TestClient, one event loop and one scheduler.
"""

import asyncio

import pytest

from app.config import settings
from app.services.telemetry import telemetry

pytestmark = pytest.mark.e2e

CHAT = "/v1/chat/completions"
POLICY = {"enforcement_mode": "enforce", "blocked_keywords": ["forbidden-word"], "pii_detection_enabled": False}


@pytest.fixture(autouse=True)
def _fresh_engines():
    """Pooled asyncpg connections are bound to the loop that created them; every lifespan gets its own."""
    from app.database import engine, system_engine

    asyncio.run(engine.dispose())
    asyncio.run(system_engine.dispose())
    yield
    telemetry.siem = telemetry.otel = None
    asyncio.run(engine.dispose())
    asyncio.run(system_engine.dispose())


def test_siem_events_reach_a_file_sink_through_the_real_lifespan(upstream, make_tenant, monkeypatch, tmp_path):
    """Startup builds the exporter, the worker runs in the app's loop, and shutdown drains the queue."""
    from fastapi.testclient import TestClient

    from app.main import app

    path = tmp_path / "siem.log"
    for key, value in (("SIEM_EXPORT_ENABLED", True), ("SIEM_FORMAT", "cef"), ("SIEM_SINK", "file"), ("SIEM_FILE_PATH", str(path))):
        monkeypatch.setattr(settings, key, value)
    tenant = make_tenant(org_settings={"policy": POLICY})
    with TestClient(app) as client:
        assert client.post(CHAT, json={"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "a forbidden-word here"}]}, headers=tenant.headers).status_code == 403
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and lines[0].startswith("CEF:0|OpenProxyAI|Gateway|1.0|AI-DLP-BLOCK|")
    assert "reason=blocked_keyword" in lines[0] and "forbidden-word" not in lines[0]


def test_bad_telemetry_configuration_stops_startup(upstream, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setattr(settings, "SIEM_EXPORT_ENABLED", True)
    monkeypatch.setattr(settings, "SIEM_FORMAT", "xml")
    with pytest.raises(ValueError, match="SIEM_FORMAT"):
        with TestClient(app):
            pass
