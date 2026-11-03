"""Real per-stage timings of one chat request, for the request trace page (P1-13).

Each stage is recorded as ``{"name", "start_ms", "ms"}``, offsets measured from the start of the
request, and stored in ``request_logs.request_metadata["stages"]``. Stages are only the ones the
gateway runs itself (policy, rate_limit, cache, upstream); a stage that did not run is absent, so a
cache hit has no ``upstream`` and a policy block stops after ``policy``. Authentication happens in a
dependency before the pipeline starts and is not timed.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class StageTimer:
	"""Collects the stages of a single request. One per request context; never shared."""

	origin: float
	_spans: list[dict[str, int | str]] = field(default_factory=list)

	@contextmanager
	def stage(self, name: str) -> Iterator[None]:
		"""Time the enclosed block. The span is recorded even when the block raises."""
		began = time.perf_counter()
		try:
			yield
		finally:
			self._spans.append({
				"name": name,
				"start_ms": round((began - self.origin) * 1000),
				"ms": round((time.perf_counter() - began) * 1000),
			})

	def as_list(self) -> list[dict[str, int | str]]:
		return [dict(span) for span in self._spans]
