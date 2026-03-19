"""Metered billing sidecar — idempotency keys, window math, Stripe usage submission."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.services import metering_service as metering_module
from app.services.metering_service import (
	MeteringService,
	clamp_window_to_subscription_period,
	meter_idempotency_key,
	run_hourly_metered_sync,
)


def test_meter_idempotency_key_format():
	org_id = uuid4()
	h = datetime(2025, 3, 1, 14, 0, tzinfo=UTC)
	assert meter_idempotency_key(org_id, h) == f"opai-meter-{org_id}-2025030114"


def test_meter_idempotency_key_naive_datetime_normalized():
	org_id = uuid4()
	h = datetime(2025, 3, 1, 14, 0)  # naive
	key = meter_idempotency_key(org_id, h)
	assert key.endswith("-2025030114")


def test_clamp_window_to_subscription_period_full_hour_inside_period():
	hour_start = datetime(2025, 3, 1, 14, 0, tzinfo=UTC)
	hour_end = datetime(2025, 3, 1, 15, 0, tzinfo=UTC)
	period_start_ts = int(datetime(2025, 3, 1, 0, 0, tzinfo=UTC).timestamp())
	now = datetime(2025, 3, 1, 16, 0, tzinfo=UTC)
	a, b = clamp_window_to_subscription_period(hour_start, hour_end, period_start_ts, now)
	assert a == hour_start
	assert b == hour_end


def test_clamp_window_late_subscription_start_trims_start():
	hour_start = datetime(2025, 3, 1, 14, 0, tzinfo=UTC)
	hour_end = datetime(2025, 3, 1, 15, 0, tzinfo=UTC)
	period_start = datetime(2025, 3, 1, 14, 30, tzinfo=UTC)
	period_start_ts = int(period_start.timestamp())
	now = datetime(2025, 3, 1, 16, 0, tzinfo=UTC)
	a, b = clamp_window_to_subscription_period(hour_start, hour_end, period_start_ts, now)
	assert a == period_start
	assert b == hour_end


def test_clamp_window_now_before_hour_end():
	hour_start = datetime(2025, 3, 1, 14, 0, tzinfo=UTC)
	hour_end = datetime(2025, 3, 1, 15, 0, tzinfo=UTC)
	period_start_ts = int(datetime(2025, 3, 1, 0, 0, tzinfo=UTC).timestamp())
	now = datetime(2025, 3, 1, 14, 30, tzinfo=UTC)
	a, b = clamp_window_to_subscription_period(hour_start, hour_end, period_start_ts, now)
	assert a == hour_start
	assert b == now


@pytest.mark.asyncio
async def test_run_hourly_metered_sync_swallows_outer_errors(monkeypatch):
	async def boom(*_a, **_k):
		raise RuntimeError("db down")

	monkeypatch.setattr(
		metering_module.metering_service,
		"sync_hourly_metered_usage",
		boom,
	)
	await run_hourly_metered_sync()


@pytest.mark.asyncio
async def test_sync_hourly_skips_when_disabled(monkeypatch):
	monkeypatch.setattr(metering_module.settings, "METERED_SYNC_ENABLED", False)
	await metering_module.metering_service.sync_hourly_metered_usage()


@pytest.mark.asyncio
async def test_submit_usage_record_invokes_stripe_static_request(monkeypatch):
	captured: dict = {}

	def fake_static_request(method, url, params=None, idempotency_key=None, **_kwargs):
		captured["method"] = method
		captured["url"] = url
		captured["params"] = dict(params or {})
		captured["idempotency_key"] = idempotency_key

	monkeypatch.setattr(metering_module.settings, "STRIPE_SECRET_KEY", "sk_test")
	monkeypatch.setattr(
		metering_module.stripe.SubscriptionItem,
		"_static_request",
		fake_static_request,
	)
	MeteringService._submit_usage_record("si_test123", 42, 1_700_000_000, "idem-key-1")
	assert captured["method"] == "post"
	assert captured["url"] == "/v1/subscription_items/si_test123/usage_records"
	assert captured["params"]["quantity"] == 42
	assert captured["params"]["timestamp"] == 1_700_000_000
	assert captured["params"]["action"] == "increment"
	# idempotency_key must be a kwarg (SDK header), NOT in the params body
	assert "idempotency_key" not in captured["params"]
	assert captured["idempotency_key"] == "idem-key-1"


@pytest.mark.asyncio
async def test_sync_one_org_hourly_token_aggregation_math(monkeypatch):
	"""Two requests in the effective window sum to one Stripe usage quantity."""
	org_id = uuid4()
	org = SimpleNamespace(
		id=org_id,
		stripe_subscription_id="sub_x",
		settings={},
	)
	hour_start = datetime(2025, 3, 1, 14, 0, tzinfo=UTC)
	hour_end = datetime(2025, 3, 1, 15, 0, tzinfo=UTC)
	now = datetime(2025, 3, 1, 16, 0, tzinfo=UTC)
	period_start_ts = int(datetime(2025, 3, 1, 0, 0, tzinfo=UTC).timestamp())

	fake_sub = {
		"current_period_start": period_start_ts,
		"current_period_end": int(datetime(2025, 3, 31, 23, 59, tzinfo=UTC).timestamp()),
		"items": {
			"data": [
				{"id": "si_metered", "price": {"id": "price_metered_test"}},
			]
		},
	}

	monkeypatch.setattr(metering_module.settings, "STRIPE_SECRET_KEY", "sk_test")
	monkeypatch.setattr(metering_module.settings, "STRIPE_METERED_PRICE_ID", "price_metered_test")

	token_calls: list[tuple] = []

	async def fake_tokens(_self, _db, oid, ws, we):
		token_calls.append((oid, ws, we))
		return 10_000 + 20_000

	async def fake_period(_self, *_a, **_k):
		return 999

	monkeypatch.setattr(
		MeteringService,
		"_retrieve_subscription",
		staticmethod(lambda _sid: fake_sub),
	)
	monkeypatch.setattr(MeteringService, "_tokens_in_window", fake_tokens)
	monkeypatch.setattr(MeteringService, "_request_logs_tokens_period", fake_period)

	stripe_calls: list[dict] = []

	def fake_submit(si_id, qty, ts, idem):
		stripe_calls.append(
			{"si_id": si_id, "qty": qty, "ts": ts, "idem": idem},
		)

	monkeypatch.setattr(MeteringService, "_submit_usage_record", staticmethod(fake_submit))

	mock_db = MagicMock()

	@asynccontextmanager
	async def _fake_session_local():
		yield mock_db

	monkeypatch.setattr(metering_module, "AsyncSessionLocal", lambda: _fake_session_local())

	async def _noop_set_session(_db, _oid):
		return None

	monkeypatch.setattr(metering_module, "set_session_org_id", _noop_set_session)

	await MeteringService()._sync_one_org(org, hour_start, hour_end, now)

	assert len(token_calls) == 1
	assert stripe_calls[0]["qty"] == 30_000
	assert stripe_calls[0]["si_id"] == "si_metered"
	assert stripe_calls[0]["idem"] == meter_idempotency_key(org_id, hour_start)


@pytest.mark.asyncio
async def test_resolve_metered_subscription_item_id_prefers_live_items_over_stale_cache(monkeypatch):
	monkeypatch.setattr(metering_module.settings, "STRIPE_METERED_PRICE_ID", "price_m")
	sub = {
		"items": {
			"data": [
				{"id": "si_fresh", "price": {"id": "price_m"}},
			]
		}
	}
	si = MeteringService._resolve_metered_subscription_item_id(sub, "si_stale")
	assert si == "si_fresh"
