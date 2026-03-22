"""Plan enforcement tests — per-org plan feature gates (Track A.2)."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.config import PLAN_FEATURES, settings as config_settings
from app.dependencies import get_current_user_from_jwt, get_db, get_redis
from app.main import app
from app.services import invite_service
from app.services.plan_service import (
    assert_plan_allows,
    check_api_key_limit,
    check_user_limit,
    get_plan_feature,
    included_tokens_monthly_for_org,
)
from app.services.policy_service import PolicyConfig
from app.services import policy_service as policy_service_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _org(plan: str = "free"):
    return SimpleNamespace(id=uuid4(), plan=plan, name="Test Org", slug="test-org")


def _admin_user(org_id=None):
    return SimpleNamespace(
        id=uuid4(),
        org_id=org_id or uuid4(),
        email="admin@test.com",
        name="Admin",
        role="admin",
        is_active=True,
    )


class FakeDB:
    """Minimal async DB stub for plan enforcement tests."""

    def __init__(self, *, get_results=None, scalar_result=None, execute_result=None):
        self._get_results = get_results or {}
        self.scalar_result = scalar_result
        self._execute_result = execute_result
        self.added = []
        self.committed = False
        self.flushed = False

    async def get(self, model_class, pk):  # noqa: ARG002
        return self._get_results.get(pk)

    async def scalar(self, query):  # noqa: ARG002
        return self.scalar_result

    async def execute(self, query):  # noqa: ARG002
        return self._execute_result

    async def scalars(self, query):  # noqa: ARG002
        return _FakeScalarResult([])

    def add(self, model):
        self.added.append(model)

    async def flush(self):
        self.flushed = True

    async def commit(self):
        self.committed = True

    async def refresh(self, model):  # noqa: ARG002
        pass


class _FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)


class _FakeExecuteResult:
    """Mimics SQLAlchemy Result to provide scalar_one()."""

    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value


class FakeRedis:
    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> bool:  # noqa: ARG002
        self._store[key] = value
        return True

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                deleted += 1
        return deleted


# ===========================================================================
# Unit tests — get_plan_feature
# ===========================================================================


class TestGetPlanFeature:
    """get_plan_feature returns correct values for each plan tier."""

    def test_free_plan_features(self):
        org = _org("free")
        assert get_plan_feature(org, "max_users") == 3
        assert get_plan_feature(org, "max_api_keys") == 5
        assert get_plan_feature(org, "sso_enabled") is False
        assert get_plan_feature(org, "pii_detection") is False
        assert get_plan_feature(org, "audit_retention_days") == 7

    def test_starter_plan_features(self):
        org = _org("starter")
        assert get_plan_feature(org, "max_users") == 50
        assert get_plan_feature(org, "max_api_keys") == 50
        assert get_plan_feature(org, "sso_enabled") is False
        assert get_plan_feature(org, "pii_detection") is True
        assert get_plan_feature(org, "audit_retention_days") == 30

    def test_growth_plan_features(self):
        org = _org("growth")
        assert get_plan_feature(org, "max_users") == 200
        assert get_plan_feature(org, "max_api_keys") == 200
        assert get_plan_feature(org, "pii_detection") is True
        assert get_plan_feature(org, "audit_retention_days") == 90

    def test_enterprise_plan_features(self):
        org = _org("enterprise")
        assert get_plan_feature(org, "max_users") == -1
        assert get_plan_feature(org, "max_api_keys") == -1
        assert get_plan_feature(org, "sso_enabled") is True
        assert get_plan_feature(org, "pii_detection") is True
        assert get_plan_feature(org, "audit_retention_days") == 365

    def test_unknown_plan_falls_back_to_free(self):
        org = _org("nonexistent")
        assert get_plan_feature(org, "max_users") == 3

    def test_none_plan_falls_back_to_free(self):
        org = SimpleNamespace(id=uuid4(), plan=None)
        assert get_plan_feature(org, "max_users") == 3

    def test_unknown_feature_returns_none(self):
        org = _org("free")
        assert get_plan_feature(org, "nonexistent_feature") is None


# ===========================================================================
# Unit tests — check_user_limit
# ===========================================================================


class TestCheckUserLimit:
    """check_user_limit raises HTTP 402 when user count meets or exceeds max."""

    def test_free_plan_at_limit_raises_402(self):
        org = _org("free")
        with pytest.raises(HTTPException) as exc_info:
            check_user_limit(org, current_count=3)
        assert exc_info.value.status_code == 402
        assert exc_info.value.detail["error"] == "plan_limit_exceeded"
        assert exc_info.value.detail["feature"] == "max_users"
        assert exc_info.value.detail["plan"] == "free"

    def test_free_plan_above_limit_raises_402(self):
        org = _org("free")
        with pytest.raises(HTTPException) as exc_info:
            check_user_limit(org, current_count=10)
        assert exc_info.value.status_code == 402

    def test_free_plan_below_limit_passes(self):
        org = _org("free")
        check_user_limit(org, current_count=2)  # should not raise

    def test_enterprise_unlimited_users_never_raises(self):
        org = _org("enterprise")
        check_user_limit(org, current_count=10_000)  # should not raise

    def test_starter_plan_at_limit_raises_402(self):
        org = _org("starter")
        with pytest.raises(HTTPException) as exc_info:
            check_user_limit(org, current_count=50)
        assert exc_info.value.status_code == 402
        assert exc_info.value.detail["feature"] == "max_users"


# ===========================================================================
# Unit tests — check_api_key_limit
# ===========================================================================


class TestCheckApiKeyLimit:
    """check_api_key_limit raises HTTP 402 when key count meets or exceeds max."""

    def test_free_plan_at_limit_raises_402(self):
        org = _org("free")
        with pytest.raises(HTTPException) as exc_info:
            check_api_key_limit(org, current_count=5)
        assert exc_info.value.status_code == 402
        assert exc_info.value.detail["error"] == "plan_limit_exceeded"
        assert exc_info.value.detail["feature"] == "max_api_keys"
        assert exc_info.value.detail["plan"] == "free"

    def test_free_plan_above_limit_raises_402(self):
        org = _org("free")
        with pytest.raises(HTTPException) as exc_info:
            check_api_key_limit(org, current_count=20)
        assert exc_info.value.status_code == 402

    def test_free_plan_below_limit_passes(self):
        org = _org("free")
        check_api_key_limit(org, current_count=4)  # should not raise

    def test_enterprise_unlimited_keys_never_raises(self):
        org = _org("enterprise")
        check_api_key_limit(org, current_count=100_000)  # should not raise

    def test_growth_plan_at_limit_raises_402(self):
        org = _org("growth")
        with pytest.raises(HTTPException) as exc_info:
            check_api_key_limit(org, current_count=200)
        assert exc_info.value.status_code == 402
        assert exc_info.value.detail["feature"] == "max_api_keys"


# ===========================================================================
# Unit tests — assert_plan_allows
# ===========================================================================


class TestAssertPlanAllows:
    """assert_plan_allows raises HTTP 402 for disabled boolean features."""

    def test_free_plan_pii_detection_raises_402(self):
        org = _org("free")
        with pytest.raises(HTTPException) as exc_info:
            assert_plan_allows(org, "pii_detection")
        assert exc_info.value.status_code == 402
        assert exc_info.value.detail["error"] == "plan_limit_exceeded"
        assert exc_info.value.detail["feature"] == "pii_detection"

    def test_starter_plan_pii_detection_passes(self):
        org = _org("starter")
        assert_plan_allows(org, "pii_detection")  # should not raise

    def test_free_plan_sso_raises_402(self):
        org = _org("free")
        with pytest.raises(HTTPException) as exc_info:
            assert_plan_allows(org, "sso_enabled")
        assert exc_info.value.status_code == 402
        assert exc_info.value.detail["feature"] == "sso_enabled"

    def test_enterprise_sso_passes(self):
        org = _org("enterprise")
        assert_plan_allows(org, "sso_enabled")  # should not raise

    def test_numeric_feature_does_not_raise(self):
        """Non-boolean features (like max_users=3) should not trigger 402."""
        org = _org("free")
        assert_plan_allows(org, "max_users")  # 3 is not False, should not raise

    def test_metered_plan_pii_detection_passes(self):
        org = _org("metered")
        assert_plan_allows(org, "pii_detection")


class TestIncludedTokensMonthly:
    def test_included_tokens_none_for_non_metered(self):
        assert included_tokens_monthly_for_org(_org("growth")) is None

    def test_included_tokens_for_metered_uses_settings(self, monkeypatch):
        monkeypatch.setattr(config_settings, "METERED_INCLUDED_TOKENS_MONTHLY", 2_000_000)
        assert included_tokens_monthly_for_org(_org("metered")) == 2_000_000


# ===========================================================================
# Integration tests — invite accept with plan enforcement
# ===========================================================================


class TestInviteAcceptPlanEnforcement:
    """accept_invite enforces per-plan user limits."""

    def test_free_org_4th_invite_returns_402(self, monkeypatch):
        """Free org accepting 4th invite raises HTTP 402 plan_limit_exceeded."""
        import asyncio
        from datetime import UTC, datetime, timedelta

        org_id = uuid4()
        org = _org("free")
        org.id = org_id

        # Naive UTC to match invite_service's now (DB timestamp columns)
        now = datetime.now(UTC).replace(tzinfo=None)
        invite = SimpleNamespace(
            id=uuid4(),
            org_id=org_id,
            email="new@test.com",
            role="developer",
            token_hash="testhash",
            invited_by=uuid4(),
            expires_at=now + timedelta(days=7),
            accepted_at=None,
        )

        db = FakeDB(
            scalar_result=invite,
            get_results={org_id: org},
            execute_result=_FakeExecuteResult(3),  # 3 active users already
        )

        monkeypatch.setattr(invite_service, "_hash_token", lambda t: "testhash")

        async def run():
            return await invite_service.accept_invite(
                db=db, token="sometoken", name="New User", password="securepass123"
            )

        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(run())

        assert exc_info.value.status_code == 402
        assert exc_info.value.detail["error"] == "plan_limit_exceeded"
        assert exc_info.value.detail["feature"] == "max_users"

    def test_enterprise_org_unlimited_users_no_402(self, monkeypatch):
        """Enterprise org (max_users=-1) can add unlimited users without 402."""
        import asyncio
        from datetime import UTC, datetime, timedelta

        org_id = uuid4()
        org = _org("enterprise")
        org.id = org_id

        # Naive UTC to match invite_service's now (DB timestamp columns)
        now = datetime.now(UTC).replace(tzinfo=None)
        invite = SimpleNamespace(
            id=uuid4(),
            org_id=org_id,
            email="new@test.com",
            role="developer",
            token_hash="testhash",
            invited_by=uuid4(),
            expires_at=now + timedelta(days=7),
            accepted_at=None,
        )

        # Simulate 500 existing users — enterprise should not block
        # After the user limit check, accept_invite will check for existing email.
        # We chain scalar calls: first returns the invite, second returns None (no dup).
        call_count = 0

        async def multi_scalar(self, query):  # noqa: ARG001
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return invite  # invite lookup
            return None  # email duplicate check (no duplicate)

        db = FakeDB(
            get_results={org_id: org},
            execute_result=_FakeExecuteResult(500),
        )
        db.scalar = multi_scalar.__get__(db)

        monkeypatch.setattr(invite_service, "_hash_token", lambda t: "testhash")

        async def run():
            return await invite_service.accept_invite(
                db=db, token="sometoken", name="New User", password="securepass123"
            )

        # Should not raise — enterprise has unlimited users
        # (It will fail later at User() construction because User is a real model,
        # but we just need to verify no 402 is raised.)
        try:
            asyncio.get_event_loop().run_until_complete(run())
        except HTTPException as exc:
            # Must not be a 402
            assert exc.status_code != 402
        except Exception:
            # Any non-HTTPException error is fine — we just verify no 402
            pass


# ===========================================================================
# Integration tests — API key creation with plan enforcement
# ===========================================================================


class TestApiKeyCreationPlanEnforcement:
    """POST /api/v1/api-keys enforces per-plan API key limits."""

    def test_free_org_6th_key_returns_402(self, client, monkeypatch):
        """Free org creating 6th API key returns HTTP 402."""
        org_id = uuid4()
        org = _org("free")
        org.id = org_id
        user = _admin_user(org_id)

        async def fake_current_user_dep():
            return user

        async def fake_get_db():
            yield FakeDB(
                get_results={org_id: org},
                execute_result=_FakeExecuteResult(5),  # 5 active keys already
            )

        app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
        app.dependency_overrides[get_db] = fake_get_db

        response = client.post(
            "/api/v1/api-keys",
            headers={"Authorization": "Bearer test"},
            json={"name": "test-key"},
        )

        assert response.status_code == 402
        data = response.json()["detail"]
        assert data["error"] == "plan_limit_exceeded"
        assert data["feature"] == "max_api_keys"

    def test_starter_org_below_limit_does_not_block(self, client, monkeypatch):
        """Starter org with keys below limit should not get 402."""
        from datetime import datetime, timezone

        from app.services import auth_service

        org_id = uuid4()
        org = _org("starter")
        org.id = org_id
        user = _admin_user(org_id)

        created_key = SimpleNamespace(
            id=uuid4(),
            user_id=user.id,
            org_id=org_id,
            key_hash="hash",
            key_prefix="opai_dev_",
            name="test-key",
            permissions=["proxy:llm"],
            is_active=True,
            last_used_at=None,
            expires_at=None,
            created_at=datetime.now(timezone.utc),
        )

        async def fake_current_user_dep():
            return user

        async def fake_get_db():
            yield FakeDB(
                get_results={org_id: org},
                execute_result=_FakeExecuteResult(10),  # 10 keys, limit is 50
            )

        async def fake_create_api_key(**kwargs):
            return created_key, "opai_dev_abc123"

        monkeypatch.setattr(auth_service, "create_api_key", fake_create_api_key)
        # Also monkeypatch in the routes module
        from app.routes import api_keys as api_keys_routes
        monkeypatch.setattr(api_keys_routes, "create_api_key", fake_create_api_key)

        app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
        app.dependency_overrides[get_db] = fake_get_db

        response = client.post(
            "/api/v1/api-keys",
            headers={"Authorization": "Bearer test"},
            json={"name": "test-key"},
        )

        assert response.status_code == 201


# ===========================================================================
# Integration tests — policy PII detection with plan enforcement
# ===========================================================================


class TestPolicyPiiPlanEnforcement:
    """PATCH /current/policy enforces plan gate for pii_detection."""

    def test_free_org_enable_pii_returns_402(self, client, monkeypatch):
        """Free org enabling pii_detection in policy returns HTTP 402."""
        org_id = uuid4()
        org = _org("free")
        org.id = org_id
        user = _admin_user(org_id)

        async def fake_current_user_dep():
            return user

        async def fake_get_db():
            yield FakeDB(get_results={org_id: org})

        async def fake_get_redis():
            return FakeRedis()

        app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_redis] = fake_get_redis

        response = client.patch(
            "/api/v1/organizations/current/policy",
            headers={"Authorization": "Bearer test"},
            json={"pii_detection_enabled": True},
        )

        assert response.status_code == 402
        data = response.json()["detail"]
        assert data["error"] == "plan_limit_exceeded"
        assert data["feature"] == "pii_detection"
        assert data["plan"] == "free"

    def test_starter_org_enable_pii_succeeds(self, client, monkeypatch):
        """Starter org enabling pii_detection in policy succeeds (starter has pii_detection=True)."""
        org_id = uuid4()
        org = _org("starter")
        org.id = org_id
        user = _admin_user(org_id)
        saved: list = []

        async def fake_current_user_dep():
            return user

        async def fake_get_db():
            yield FakeDB(get_results={org_id: org})

        async def fake_get_redis():
            return FakeRedis()

        async def fake_load(org_id, db, redis):  # noqa: ANN001
            return PolicyConfig(
                enforcement_mode="off",
                allowed_models=[],
                blocked_keywords=[],
                pii_detection_enabled=False,
                pii_entities=[],
            )

        async def fake_save(org_id, config, db, redis):  # noqa: ANN001
            saved.append(config)

        monkeypatch.setattr(policy_service_module.policy_store, "load", fake_load)
        monkeypatch.setattr(policy_service_module.policy_store, "save", fake_save)
        app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_redis] = fake_get_redis

        response = client.patch(
            "/api/v1/organizations/current/policy",
            headers={"Authorization": "Bearer test"},
            json={"pii_detection_enabled": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pii_detection_enabled"] is True
        assert len(saved) == 1

    def test_patch_policy_without_pii_field_skips_plan_check(self, client, monkeypatch):
        """Patching policy without pii_detection_enabled should not trigger plan check."""
        org_id = uuid4()
        org = _org("free")
        org.id = org_id
        user = _admin_user(org_id)

        async def fake_current_user_dep():
            return user

        async def fake_get_db():
            yield FakeDB(get_results={org_id: org})

        async def fake_get_redis():
            return FakeRedis()

        async def fake_load(org_id, db, redis):  # noqa: ANN001
            return PolicyConfig(
                enforcement_mode="off",
                allowed_models=[],
                blocked_keywords=[],
                pii_detection_enabled=False,
                pii_entities=[],
            )

        async def fake_save(org_id, config, db, redis):  # noqa: ANN001
            pass

        monkeypatch.setattr(policy_service_module.policy_store, "load", fake_load)
        monkeypatch.setattr(policy_service_module.policy_store, "save", fake_save)
        app.dependency_overrides[get_current_user_from_jwt] = fake_current_user_dep
        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_redis] = fake_get_redis

        response = client.patch(
            "/api/v1/organizations/current/policy",
            headers={"Authorization": "Bearer test"},
            json={"enforcement_mode": "log_only"},
        )

        # Should succeed — no pii check for free plan when pii field is not in payload
        assert response.status_code == 200


# ===========================================================================
# PLAN_FEATURES integrity
# ===========================================================================


class TestPlanFeaturesIntegrity:
    """Verify the PLAN_FEATURES dict has all required tiers and keys."""

    def test_all_plans_present(self):
        assert set(PLAN_FEATURES.keys()) == {"free", "starter", "growth", "enterprise", "metered"}

    def test_all_plans_have_same_keys(self):
        expected_keys = {
            "max_users",
            "max_api_keys",
            "sso_enabled",
            "pii_detection",
            "audit_retention_days",
            "included_tokens_monthly",
        }
        for plan, features in PLAN_FEATURES.items():
            assert set(features.keys()) == expected_keys, f"Plan '{plan}' has wrong keys"

    def test_enterprise_has_unlimited_users_and_keys(self):
        assert PLAN_FEATURES["enterprise"]["max_users"] == -1
        assert PLAN_FEATURES["enterprise"]["max_api_keys"] == -1

    def test_free_plan_is_most_restrictive(self):
        free = PLAN_FEATURES["free"]
        for plan_name, features in PLAN_FEATURES.items():
            if plan_name == "free":
                continue
            max_u = features["max_users"]
            # Enterprise is -1 (unlimited), others should be >= free
            if max_u != -1:
                assert max_u >= free["max_users"]
