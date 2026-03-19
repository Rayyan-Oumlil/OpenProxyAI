"""Billing route tests — checkout, portal, and Stripe webhook processing."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.dependencies import get_current_user_from_jwt, get_db
from app.main import app
from app.services import billing_service as billing_module


class _FakeExecuteResult:
    """Mimics SQLAlchemy CursorResult for INSERT ... ON CONFLICT DO NOTHING."""

    def __init__(self, rowcount: int):
        self.rowcount = rowcount


class FakeDB:
    def __init__(self, *, get_result=None, scalar_results=None, insert_rowcounts=None):
        self._get_result = get_result
        self._scalar_results = list(scalar_results or [])
        self._insert_rowcounts = list(insert_rowcounts or [1])
        self.added = []
        self.commit_count = 0

    async def get(self, model_cls, pk):  # noqa: ARG002
        return self._get_result

    async def scalar(self, *args, **kwargs):  # noqa: ARG002
        if self._scalar_results:
            return self._scalar_results.pop(0)
        return None

    async def execute(self, *args, **kwargs):  # noqa: ARG002
        rc = self._insert_rowcounts.pop(0) if self._insert_rowcounts else 1
        return _FakeExecuteResult(rc)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        return None

    async def refresh(self, obj):  # noqa: ARG002
        return None

    async def commit(self):
        self.commit_count += 1


def _make_org(org_id=None, *, plan="free", customer_id=None, subscription_id=None, sub_status=None):
    return SimpleNamespace(
        id=org_id or uuid4(),
        name="Acme",
        slug="acme",
        plan=plan,
        settings={},
        budget_monthly_usd=None,
        is_active=True,
        data_region="us-east-1",
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        stripe_subscription_status=sub_status,
    )


def _make_user(org_id, role="admin"):
    return SimpleNamespace(
        id=uuid4(),
        org_id=org_id,
        email="admin@test.com",
        role=role,
        is_active=True,
    )


def _override_auth(user):
    async def dep():
        return user

    app.dependency_overrides[get_current_user_from_jwt] = dep


def _override_db(db_instance):
    async def dep():
        yield db_instance

    app.dependency_overrides[get_db] = dep


def _set_stripe_config(monkeypatch):
    monkeypatch.setattr(billing_module.settings, "STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(billing_module.settings, "STRIPE_WEBHOOK_SECRET", "whsec_123")
    monkeypatch.setattr(billing_module.settings, "STRIPE_STARTER_PRICE_ID", "price_starter")
    monkeypatch.setattr(billing_module.settings, "STRIPE_GROWTH_PRICE_ID", "price_growth")
    monkeypatch.setattr(billing_module.settings, "STRIPE_SUCCESS_URL", "http://localhost:5173/billing?success=1")
    monkeypatch.setattr(billing_module.settings, "STRIPE_CANCEL_URL", "http://localhost:5173/billing?canceled=1")


def test_checkout_returns_url(client, monkeypatch):
    _set_stripe_config(monkeypatch)
    org = _make_org()
    user = _make_user(org.id, role="admin")
    db = FakeDB(get_result=org, scalar_results=[org])
    _override_auth(user)
    _override_db(db)

    monkeypatch.setattr(
        billing_module.stripe.Customer,
        "create",
        lambda **kwargs: {"id": "cus_123"},
    )
    monkeypatch.setattr(
        billing_module.stripe.checkout.Session,
        "create",
        lambda **kwargs: {"url": "https://checkout.stripe.test/session_123"},
    )

    response = client.post(
        "/api/v1/billing/checkout",
        json={"plan": "starter"},
        headers={"Authorization": "Bearer test"},
    )
    assert response.status_code == 200
    assert response.json()["checkout_url"] == "https://checkout.stripe.test/session_123"


def test_checkout_requires_admin(client):
    org = _make_org()
    user = _make_user(org.id, role="developer")
    _override_auth(user)
    _override_db(FakeDB(get_result=org))
    response = client.post(
        "/api/v1/billing/checkout",
        json={"plan": "starter"},
        headers={"Authorization": "Bearer test"},
    )
    assert response.status_code == 403


def test_checkout_requires_auth(client):
    response = client.post("/api/v1/billing/checkout", json={"plan": "starter"})
    assert response.status_code == 401


def test_checkout_enterprise_rejected(client, monkeypatch):
    _set_stripe_config(monkeypatch)
    org = _make_org()
    user = _make_user(org.id, role="admin")
    _override_auth(user)
    _override_db(FakeDB(get_result=org))
    response = client.post(
        "/api/v1/billing/checkout",
        json={"plan": "enterprise"},
        headers={"Authorization": "Bearer test"},
    )
    assert response.status_code == 400


def test_checkout_stripe_not_configured(client, monkeypatch):
    monkeypatch.setattr(billing_module.settings, "STRIPE_SECRET_KEY", "")
    org = _make_org()
    user = _make_user(org.id, role="admin")
    _override_auth(user)
    _override_db(FakeDB(get_result=org))
    response = client.post(
        "/api/v1/billing/checkout",
        json={"plan": "starter"},
        headers={"Authorization": "Bearer test"},
    )
    assert response.status_code == 400


def test_portal_returns_url(client, monkeypatch):
    _set_stripe_config(monkeypatch)
    org = _make_org(customer_id="cus_123")
    user = _make_user(org.id, role="admin")
    _override_auth(user)
    _override_db(FakeDB(get_result=org, scalar_results=[org]))
    monkeypatch.setattr(
        billing_module.stripe.billing_portal.Session,
        "create",
        lambda **kwargs: {"url": "https://billing.stripe.test/portal_123"},
    )
    response = client.post("/api/v1/billing/portal", headers={"Authorization": "Bearer test"})
    assert response.status_code == 200
    assert response.json()["portal_url"] == "https://billing.stripe.test/portal_123"


def test_portal_400_if_no_customer(client, monkeypatch):
    _set_stripe_config(monkeypatch)
    org = _make_org(customer_id=None)
    user = _make_user(org.id, role="admin")
    _override_auth(user)
    _override_db(FakeDB(get_result=org, scalar_results=[org]))
    response = client.post("/api/v1/billing/portal", headers={"Authorization": "Bearer test"})
    assert response.status_code == 400


def test_webhook_invalid_signature_returns_400(client, monkeypatch):
    _set_stripe_config(monkeypatch)
    _override_db(FakeDB())
    monkeypatch.setattr(
        billing_module.stripe.Webhook,
        "construct_event",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("bad sig")),
    )
    response = client.post(
        "/api/v1/billing/webhook",
        headers={"Stripe-Signature": "bad"},
        content=b"{}",
    )
    assert response.status_code == 400


def test_webhook_idempotency(client, monkeypatch):
    _set_stripe_config(monkeypatch)
    org = _make_org(customer_id="cus_123")
    db = FakeDB(
        scalar_results=[org, org],
        insert_rowcounts=[1, 0],
    )
    _override_db(db)

    monkeypatch.setattr(
        billing_module.stripe.Webhook,
        "construct_event",
        lambda **kwargs: {
            "id": "evt_1",
            "type": "invoice.payment_failed",
            "data": {"object": {"customer": "cus_123"}},
        },
    )

    response1 = client.post(
        "/api/v1/billing/webhook",
        headers={"Stripe-Signature": "ok"},
        content=b"{}",
    )
    response2 = client.post(
        "/api/v1/billing/webhook",
        headers={"Stripe-Signature": "ok"},
        content=b"{}",
    )
    assert response1.status_code == 200
    assert response2.status_code == 200
    assert db.commit_count == 1


def test_webhook_invoice_paid_syncs_plan(client, monkeypatch):
    _set_stripe_config(monkeypatch)
    org = _make_org(plan="free", customer_id="cus_123", sub_status="past_due")
    db = FakeDB(scalar_results=[org])
    _override_db(db)
    monkeypatch.setattr(
        billing_module.stripe.Webhook,
        "construct_event",
        lambda **kwargs: {
            "id": "evt_2",
            "type": "invoice.paid",
            "data": {
                "object": {
                    "customer": "cus_123",
                    "lines": {"data": [{"price": {"id": "price_growth"}}]},
                }
            },
        },
    )
    response = client.post(
        "/api/v1/billing/webhook",
        headers={"Stripe-Signature": "ok"},
        content=b"{}",
    )
    assert response.status_code == 200
    assert org.plan == "growth"
    assert org.stripe_subscription_status == "active"


def test_webhook_payment_failed_sets_past_due(client, monkeypatch):
    _set_stripe_config(monkeypatch)
    org = _make_org(plan="starter", customer_id="cus_123", sub_status="active")
    db = FakeDB(scalar_results=[org])
    _override_db(db)
    monkeypatch.setattr(
        billing_module.stripe.Webhook,
        "construct_event",
        lambda **kwargs: {
            "id": "evt_3",
            "type": "invoice.payment_failed",
            "data": {"object": {"customer": "cus_123"}},
        },
    )
    response = client.post(
        "/api/v1/billing/webhook",
        headers={"Stripe-Signature": "ok"},
        content=b"{}",
    )
    assert response.status_code == 200
    assert org.stripe_subscription_status == "past_due"


def test_webhook_subscription_deleted_downgrades_to_free(client, monkeypatch):
    _set_stripe_config(monkeypatch)
    org = _make_org(
        plan="growth",
        customer_id="cus_123",
        subscription_id="sub_123",
        sub_status="active",
    )
    db = FakeDB(scalar_results=[org])
    _override_db(db)
    monkeypatch.setattr(
        billing_module.stripe.Webhook,
        "construct_event",
        lambda **kwargs: {
            "id": "evt_4",
            "type": "customer.subscription.deleted",
            "data": {"object": {"customer": "cus_123"}},
        },
    )
    response = client.post(
        "/api/v1/billing/webhook",
        headers={"Stripe-Signature": "ok"},
        content=b"{}",
    )
    assert response.status_code == 200
    assert org.plan == "free"
    assert org.stripe_subscription_id is None
    assert org.stripe_subscription_status == "canceled"


def test_webhook_unknown_price_id_does_not_change_plan(client, monkeypatch):
    _set_stripe_config(monkeypatch)
    org = _make_org(plan="starter", customer_id="cus_123")
    db = FakeDB(scalar_results=[org])
    _override_db(db)
    monkeypatch.setattr(
        billing_module.stripe.Webhook,
        "construct_event",
        lambda **kwargs: {
            "id": "evt_5",
            "type": "invoice.paid",
            "data": {
                "object": {
                    "customer": "cus_123",
                    "lines": {"data": [{"price": {"id": "price_unknown"}}]},
                }
            },
        },
    )
    response = client.post(
        "/api/v1/billing/webhook",
        headers={"Stripe-Signature": "ok"},
        content=b"{}",
    )
    assert response.status_code == 200
    assert org.plan == "starter"


def test_webhook_subscription_updated_syncs_plan(client, monkeypatch):
    _set_stripe_config(monkeypatch)
    org = _make_org(
        plan="starter",
        customer_id="cus_123",
        subscription_id="sub_123",
        sub_status="past_due",
    )
    db = FakeDB(scalar_results=[org])
    _override_db(db)
    monkeypatch.setattr(
        billing_module.stripe.Webhook,
        "construct_event",
        lambda **kwargs: {
            "id": "evt_sub_upd",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_123",
                    "customer": "cus_123",
                    "status": "active",
                    "items": {"data": [{"price": {"id": "price_growth"}}]},
                }
            },
        },
    )
    response = client.post(
        "/api/v1/billing/webhook",
        headers={"Stripe-Signature": "ok"},
        content=b"{}",
    )
    assert response.status_code == 200
    assert org.plan == "growth"
    assert org.stripe_subscription_status == "active"


def test_webhook_checkout_unpaid_does_not_upgrade(client, monkeypatch):
    _set_stripe_config(monkeypatch)
    db = FakeDB()
    _override_db(db)
    monkeypatch.setattr(
        billing_module.stripe.Webhook,
        "construct_event",
        lambda **kwargs: {
            "id": "evt_6",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "payment_status": "unpaid",
                    "client_reference_id": str(uuid4()),
                    "customer": "cus_123",
                    "subscription": "sub_123",
                }
            },
        },
    )
    response = client.post(
        "/api/v1/billing/webhook",
        headers={"Stripe-Signature": "ok"},
        content=b"{}",
    )
    assert response.status_code == 200
