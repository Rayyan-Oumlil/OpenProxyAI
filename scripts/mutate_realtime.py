"""Mutation check for the realtime API: each deliberate break of a rule must make the tests fail. Run inside the api container.

    docker cp scripts/mutate_realtime.py <container>:/app/ && docker exec <container> python /app/mutate_realtime.py
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path("/app")
RELAY, ROUTE = ROOT / "app/services/realtime_relay.py", ROOT / "app/routes/realtime.py"
TESTS = ["tests/test_realtime_relay.py", "tests/test_realtime_db.py"]

MUTATIONS = [
	("text is not scanned", RELAY, "			reason = await hooks.scan(text)", "			reason = None"),
	("unknown events are forwarded", RELAY, 'if event["type"] not in CLIENT_EVENTS:', 'if False:'),
	("responses are not admitted", RELAY, '			reason = await hooks.admit_response()', '			reason = None'),
	("usage recording errors are swallowed", RELAY, "				await hooks.record_response(event[\"response\"])", "				pass"),
	("message size is not limited", RELAY, "if _size(frame) > max_bytes:", "if False:"),
	("revocation is not noticed", RELAY, "		if not await hooks.still_valid():", "		if False:"),
	("a key in the URL is accepted", ROUTE, '	header = ws.headers.get("authorization", "")', '	header = "Bearer " + ws.query_params.get("api_key", "")'),
	("the session cap is not enforced", ROUTE, "> settings.REALTIME_MAX_SESSIONS_PER_ORG:", "> 10**9:"),
	("the session counter is not released", ROUTE, "		await redis.decr(counter)\n		if upstream", "		if upstream"),
	("the caller's own key is sent upstream", ROUTE, '"Authorization": f"Bearer {api_key}"', '"Authorization": f"Bearer {credential_leak}"'),
	("response guardrail orgs are let in", ROUTE, "		if config.response_guardrails_enabled and config.enforcement_mode.lower().strip() == \"enforce\":\n			return await refuse_and_log(\"response_guardrails_not_supported_in_realtime\")", "		pass"),
]


def passes() -> bool:
	run = subprocess.run([sys.executable, "-m", "pytest", *TESTS, "-q", "-x", "-p", "no:cacheprovider"], cwd=ROOT, capture_output=True, text=True, env={**__import__("os").environ, "RLS_TESTS_REQUIRED": "1"})
	return run.returncode == 0


def main() -> int:
	assert passes(), "the baseline must pass before mutating"
	survived = []
	for name, path, old, new in MUTATIONS:
		source = path.read_text(encoding="utf-8")
		assert old in source, f"mutation target not found: {name}"
		try:
			path.write_text(source.replace(old, new, 1), encoding="utf-8")
			caught = not passes()
		finally:
			path.write_text(source, encoding="utf-8")
		print(("caught   " if caught else "SURVIVED ") + name)
		if not caught:
			survived.append(name)
	return 1 if survived else 0


if __name__ == "__main__":
	raise SystemExit(main())
