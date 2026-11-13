# ruff: noqa: F811  (fixtures are imported from the suite that defines them and then used by name)
"""Behaviour settings on the playground compare endpoint (it plans each model through the same runner)."""

from __future__ import annotations

from app.services import behavior as bh
from app.services import policy_service as ps
from app.services.policy_service import PolicyConfig
from tests.test_playground_routing import MODELS, harness  # noqa: F401  (fixture)


def test_without_behaviour_nothing_is_added(harness):
    harness.configure()
    response = harness.compare("hi")
    assert response.status_code == 200
    assert all("reasoning_effort" not in c and "temperature" not in c for c in harness.called)


def test_a_setting_reaches_every_model_and_a_ceiling_lowers_it(harness, client, monkeypatch):
    harness.configure()

    async def policy(*_a, **_k):
        return PolicyConfig(behavior_ceiling={"creativity": "medium"}, behavior_defaults={"citations": True})

    monkeypatch.setattr(ps.policy_store, "load", policy)
    response = client.post(
        "/api/v1/playground/compare", headers={"Authorization": "Bearer x"},
        json={"models": MODELS, "messages": [{"role": "user", "content": "hi"}], "behavior": {"creativity": "high"}},
    )
    assert response.status_code == 200
    assert [c["temperature"] for c in harness.called] == [bh.TEMPERATURE["medium"]] * 2
    assert all(c["messages"][0] == {"role": "system", "content": bh.CITATION_INSTRUCTION} for c in harness.called)
    assert all(log["request_metadata"]["behavior"]["clamped"] == ["creativity"] for log in harness.logs)
