"""One rule for a call LiteLLM cannot price: charge a flat fee and say so, never fail a call that already succeeded and never charge zero."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.config import settings
from app.services.cost_tracker import cost_tracker_service


def test_a_priced_call_is_priced_and_not_marked_estimated(monkeypatch):
	monkeypatch.setattr(cost_tracker_service, "calculate_cost_usd", lambda r, call_type=None: Decimal("0.5"))
	assert cost_tracker_service.price_or_fallback({"x": 1}) == (Decimal("0.5"), False)


@pytest.mark.parametrize("units,expected", [(1, "0.02"), (3, "0.06")])
def test_an_unpriced_call_costs_the_flat_fee_per_unit_and_is_marked_estimated(monkeypatch, units, expected):
	def boom(r, call_type=None):
		raise ValueError("not in the price map")

	monkeypatch.setattr(cost_tracker_service, "calculate_cost_usd", boom)
	monkeypatch.setattr(settings, "UNPRICED_CALL_COST_USD", 0.02)
	assert cost_tracker_service.price_or_fallback({}, units=units) == (Decimal(expected), True)


def test_the_call_type_is_passed_through(monkeypatch):
	seen = []
	monkeypatch.setattr(cost_tracker_service, "calculate_cost_usd", lambda r, call_type=None: seen.append(call_type) or Decimal(0))
	cost_tracker_service.price_or_fallback({}, call_type="embedding")
	assert seen == ["embedding"]
