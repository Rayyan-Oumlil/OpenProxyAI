"""Async ML-based prompt injection detector.

Model: protectai/deberta-v3-base-prompt-injection (HuggingFace)
Fallback: regex patterns from policy_service._INJECTION_PATTERNS

Fail-open contract:
  - Model unavailable / not installed → regex fallback
  - Inference timeout                 → (False, 0.0) — allow
  - Any inference exception           → (False, 0.0) — allow
"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

_MODEL_ID = "protectai/deberta-v3-base-prompt-injection"
_LOCK = asyncio.Lock()


class PromptInjectionDetector:
	"""Lazy-loading ML detector.

	Use the module-level singleton ``injection_detector`` — do not instantiate
	directly in production code.
	"""

	def __init__(self) -> None:
		self._pipeline: object | None = None
		self._model_loaded: bool = False
		self._load_attempted: bool = False

	# ── Loading ───────────────────────────────────────────────────────────────

	async def ensure_loaded(self) -> None:
		"""Lazy-load the ML model in a thread pool (idempotent)."""
		if self._load_attempted:
			return
		async with _LOCK:
			if self._load_attempted:
				return
			self._load_attempted = True
			try:
				loop = asyncio.get_event_loop()
				self._pipeline = await loop.run_in_executor(None, self._load_model_sync)
				self._model_loaded = True
				logger.info("Prompt injection ML model loaded: %s", _MODEL_ID)
			except Exception as exc:
				logger.warning(
					"Prompt injection ML model unavailable (%s); using regex fallback.",
					exc,
				)
				self._model_loaded = False

	@staticmethod
	def _load_model_sync() -> object:
		from transformers import pipeline  # type: ignore[import-untyped]

		return pipeline(
			"text-classification",
			model=_MODEL_ID,
			truncation=True,
			max_length=512,
		)

	# ── Detection ─────────────────────────────────────────────────────────────

	async def detect(self, text: str) -> tuple[bool, float]:
		"""Return ``(is_injection, confidence_score)``.

		Confidence is 0.0–1.0 from the ML model, or 1.0/0.0 from regex fallback.
		Fail-open: errors and timeouts return ``(False, 0.0)``.
		"""
		if not text:
			return False, 0.0

		from app.config import settings

		stripped = text.strip()
		if len(stripped) < settings.PROMPT_INJECTION_MIN_TEXT_LENGTH:
			# Text is too short for reliable ML classification.
			# Real injection attempts require enough words to reference and override
			# system instructions — fall through to regex patterns only.
			return self._regex_fallback(stripped)

		await self.ensure_loaded()

		if not self._model_loaded or self._pipeline is None:
			return self._regex_fallback(text)

		from app.config import settings

		try:
			loop = asyncio.get_event_loop()
			result = await asyncio.wait_for(
				loop.run_in_executor(
					None,
					lambda: self._pipeline(text[:2000]),  # type: ignore[operator]
				),
				timeout=settings.PROMPT_INJECTION_TIMEOUT_SECONDS,
			)
			label: str = result[0]["label"]
			raw_score: float = float(result[0]["score"])
			# Normalize to injection probability regardless of which label the model returns.
			# INJECTION score=0.97 → injection_prob=0.97
			# SAFE    score=0.99 → injection_prob=0.01
			injection_prob = raw_score if label == "INJECTION" else (1.0 - raw_score)
			is_injection = injection_prob >= settings.PROMPT_INJECTION_SCORE_THRESHOLD
			return is_injection, injection_prob
		except asyncio.TimeoutError:
			logger.warning(
				"Prompt injection ML inference timed out (>%.1fs); failing open.",
				settings.PROMPT_INJECTION_TIMEOUT_SECONDS,
			)
			return False, 0.0
		except Exception as exc:
			logger.error("Prompt injection ML inference error: %s; failing open.", exc)
			return False, 0.0

	# ── Regex fallback ────────────────────────────────────────────────────────

	@staticmethod
	def _regex_fallback(text: str) -> tuple[bool, float]:
		"""Regex patterns from policy_service as safety net when ML unavailable."""
		from app.services.policy_service import _INJECTION_PATTERNS

		for pattern in _INJECTION_PATTERNS:
			if pattern.search(text):
				return True, 1.0
		return False, 0.0


injection_detector = PromptInjectionDetector()
