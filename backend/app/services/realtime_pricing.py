"""Pricing a realtime response from the usage block of its ``response.done`` event.

Realtime bills audio and text tokens at different rates. When the provider gives a breakdown that adds up to its totals it is used;
otherwise every token is charged at the audio rate (the dearer one), so a missing or inconsistent breakdown can only over-charge,
never give the call away. Usage that is absent or nonsense is ``Unpriced``: the caller charges its flat fallback and says so.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


class Unpriced(Exception):
	"""No trustworthy price for this response."""


def price_table() -> dict[str, dict]:
	import litellm

	return litellm.model_cost


def _count(value: Any) -> int:
	if isinstance(value, bool) or not isinstance(value, int) or value < 0:
		raise Unpriced("usage is not a count of tokens")
	return value


def tokens_of(usage: Any) -> tuple[int, int] | None:
	try:
		return _count(usage["input_tokens"]), _count(usage["output_tokens"])
	except (Unpriced, KeyError, TypeError):
		return None


def _rates(model: str) -> dict:
	table = price_table()
	name = model.split("/", 1)[-1]
	for key in (model, name, f"openai/{name}"):
		if key in table:
			return table[key]
	raise Unpriced(f"no price for {model}")


def _split(total: int, details: Any) -> tuple[int, int | None]:
	"""(text tokens, audio tokens) when the breakdown adds up to the total; (0, None) otherwise."""
	if isinstance(details, dict):
		text, audio = details.get("text_tokens"), details.get("audio_tokens")
		if all(isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in (text, audio)) and text + audio == total:
			return text, audio
	return 0, None


def cost_usd(model: str, usage: Any) -> Decimal:
	counts = tokens_of(usage)
	if counts is None:
		raise Unpriced("the provider reported no usable usage")
	rates = _rates(model)
	total = Decimal(0)
	for count, details, text_key, audio_key in (
		(counts[0], usage.get("input_token_details"), "input_cost_per_token", "input_cost_per_audio_token"),
		(counts[1], usage.get("output_token_details"), "output_cost_per_token", "output_cost_per_audio_token"),
	):
		text_rate, audio_rate = rates.get(text_key), rates.get(audio_key, rates.get(text_key))
		if text_rate is None or audio_rate is None:
			raise Unpriced(f"no rate for {model}")
		text, audio = _split(count, details)
		if audio is None:
			text, audio = 0, count
		total += Decimal(str(text_rate)) * text + Decimal(str(audio_rate)) * audio
	return total.quantize(Decimal("0.000001"))
