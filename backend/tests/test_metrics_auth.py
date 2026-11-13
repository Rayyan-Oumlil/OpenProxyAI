"""/metrics carries per-org and per-model labels. With METRICS_BEARER_TOKEN set it needs that token."""

from __future__ import annotations

import pytest

from app.config import settings


def test_metrics_is_open_when_no_token_is_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "METRICS_BEARER_TOKEN", "", raising=False)
    assert client.get("/metrics").status_code == 200


@pytest.mark.parametrize("header", [None, "Bearer wrong", "Basic c2VjcmV0", "secret", "Bearer "])
def test_metrics_refuses_without_the_token(client, monkeypatch, header):
    monkeypatch.setattr(settings, "METRICS_BEARER_TOKEN", "secret", raising=False)
    headers = {"Authorization": header} if header is not None else {}
    response = client.get("/metrics", headers=headers)
    assert response.status_code == 401
    assert "openproxy_" not in response.text


def test_metrics_serves_with_the_token(client, monkeypatch):
    monkeypatch.setattr(settings, "METRICS_BEARER_TOKEN", "secret", raising=False)
    assert client.get("/metrics", headers={"Authorization": "Bearer secret"}).status_code == 200
