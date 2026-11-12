"""Pricing a realtime response from the usage the provider reports."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services import realtime_pricing as rp

PRICES = {"input_cost_per_token": 4e-06, "output_cost_per_token": 2.4e-05, "input_cost_per_audio_token": 3.2e-05, "output_cost_per_audio_token": 6.4e-05}


@pytest.fixture(autouse=True)
def table(monkeypatch):
	monkeypatch.setattr(rp, "price_table", lambda: {"gpt-realtime": PRICES, "gpt-text-only": {"input_cost_per_token": 1e-06, "output_cost_per_token": 2e-06}})


def usage(**parts):
	return {"input_tokens": 0, "output_tokens": 0, **parts}


def test_text_and_audio_tokens_are_priced_at_their_own_rates():
	u = usage(input_tokens=300, output_tokens=150, input_token_details={"text_tokens": 100, "audio_tokens": 200}, output_token_details={"text_tokens": 50, "audio_tokens": 100})
	expected = Decimal("100") * Decimal("4e-06") + Decimal("200") * Decimal("3.2e-05") + Decimal("50") * Decimal("2.4e-05") + Decimal("100") * Decimal("6.4e-05")
	assert rp.cost_usd("openai/gpt-realtime", u) == expected.quantize(Decimal("0.000001"))


def test_without_a_breakdown_every_token_is_priced_as_audio_the_dearer_rate_never_less_than_the_truth():
	u = usage(input_tokens=100, output_tokens=10)
	expected = (Decimal("100") * Decimal("3.2e-05") + Decimal("10") * Decimal("6.4e-05")).quantize(Decimal("0.000001"))
	assert rp.cost_usd("openai/gpt-realtime", u) == expected


def test_a_model_with_no_audio_rate_uses_its_token_rate():
	assert rp.cost_usd("openai/gpt-text-only", usage(input_tokens=1000, output_tokens=1000)) == Decimal("0.003000")


def test_an_unknown_model_is_unpriced_so_the_caller_can_charge_its_flat_fee():
	with pytest.raises(rp.Unpriced):
		rp.cost_usd("openai/never-heard-of-it", usage(input_tokens=1))


def test_a_breakdown_that_does_not_add_up_is_priced_on_the_totals_not_trusted():
	u = usage(input_tokens=100, output_tokens=0, input_token_details={"text_tokens": 1, "audio_tokens": 1})
	assert rp.cost_usd("openai/gpt-realtime", u) == (Decimal("100") * Decimal("3.2e-05")).quantize(Decimal("0.000001"))


@pytest.mark.parametrize("bad", [None, {}, {"input_tokens": "x"}, {"input_tokens": -1, "output_tokens": 0}, {"input_tokens": True, "output_tokens": 0}])
def test_usage_that_is_missing_or_nonsense_is_not_priced_as_zero(bad):
	with pytest.raises(rp.Unpriced):
		rp.cost_usd("openai/gpt-realtime", bad)


def test_tokens_of_reads_the_totals():
	assert rp.tokens_of(usage(input_tokens=7, output_tokens=3)) == (7, 3)
	assert rp.tokens_of(None) is None
