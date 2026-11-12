"""Mutation check for the shared admission gate. Run inside the api container as root (see mutate_realtime.py)."""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path("/app")
GATE = ROOT / "app/services/request_gate.py"
TESTS = ["tests/test_request_gate.py", "tests/test_chat_parity.py", "tests/test_modalities_pipeline.py", "tests/test_proxy.py", "tests/test_policy.py"]

MUTATIONS = [
	("a policy block is not refused", "	if not gate.decision.allowed:", "	if False:"),
	("a routing block is not refused", "	if gate.routing is not None and gate.routing.blocked:", "	if False:"),
	("routing runs even when off", '	if gate.config.routing_mode != "off":', "	if True:"),
	("the team step is skipped", "	team_budget = await between(gate.config, gate.classification, gate.routing)", "	team_budget = None"),
	("the rate limit is not enforced", "	if not ok:", "	if False:"),
	("the estimate can be zero", "request_tokens_estimate=max(estimate_tokens, 1)", "request_tokens_estimate=estimate_tokens"),
	("the data class header is missing", '"X-OpenProxyAI-Data-Class": gate.classification.data_class, ', ""),
	("limits see the model before routing", "model=model_of()", 'model="stale"'),
]


def passes() -> bool:
	run = subprocess.run([sys.executable, "-m", "pytest", *TESTS, "-q", "-x", "-p", "no:cacheprovider"], cwd=ROOT, capture_output=True, text=True, env={**os.environ})
	return run.returncode == 0


def main() -> int:
	assert passes(), "baseline must pass"
	survived = 0
	for name, old, new in MUTATIONS:
		source = GATE.read_text(encoding="utf-8")
		assert old in source, f"target not found: {name}"
		try:
			GATE.write_text(source.replace(old, new, 1), encoding="utf-8")
			caught = not passes()
		finally:
			GATE.write_text(source, encoding="utf-8")
		print(("caught   " if caught else "SURVIVED ") + name)
		survived += not caught
	return 1 if survived else 0


if __name__ == "__main__":
	raise SystemExit(main())
