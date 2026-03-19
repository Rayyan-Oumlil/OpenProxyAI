"""Stripe billing service: checkout, portal, and webhook processing."""

from __future__ import annotations

import uuid
from typing import Any

import stripe
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.organization import Organization
from app.models.stripe_event import StripeEvent
from app.services.admin_audit_service import log_admin_action

def _event_get(obj: Any, *path: str, default: Any = None) -> Any:
    cur = obj
    for key in path:
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            cur = getattr(cur, key, None)
    return default if cur is None else cur


class BillingService:
    @staticmethod
    def _require_stripe_enabled() -> None:
        if not settings.STRIPE_SECRET_KEY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stripe is not configured",
            )
        stripe.api_key = settings.STRIPE_SECRET_KEY

    @staticmethod
    def _price_id_for_plan(plan: str) -> str:
        plan_key = plan.lower().strip()
        if plan_key == "starter":
            return settings.STRIPE_STARTER_PRICE_ID
        if plan_key == "growth":
            return settings.STRIPE_GROWTH_PRICE_ID
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported plan: {plan}",
        )

    @staticmethod
    def _plan_for_price_id(price_id: str | None) -> str | None:
        if not price_id:
            return None
        if price_id == settings.STRIPE_STARTER_PRICE_ID and price_id:
            return "starter"
        if price_id == settings.STRIPE_GROWTH_PRICE_ID and price_id:
            return "growth"
        return None

    @staticmethod
    async def _log_plan_change(
        db: AsyncSession,
        *,
        org: Organization,
        before_plan: str,
        action: str,
        event_id: str,
    ) -> None:
        if before_plan == org.plan:
            return
        await log_admin_action(
            db,
            org_id=org.id,
            actor_id=None,
            actor_email="stripe-webhook",
            action=action,
            resource_type="organization",
            resource_id=str(org.id),
            before={"plan": before_plan, "event_id": event_id},
            after={"plan": org.plan, "event_id": event_id},
            ip_address=None,
        )

    async def get_or_create_customer(self, org: Organization, db: AsyncSession) -> str:
        self._require_stripe_enabled()
        locked_org = await db.scalar(
            select(Organization).where(Organization.id == org.id).with_for_update()
        )
        if locked_org is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found",
            )
        if locked_org.stripe_customer_id:
            return locked_org.stripe_customer_id

        customer = stripe.Customer.create(
            name=locked_org.name,
            metadata={"org_id": str(locked_org.id)},
        )
        customer_id = _event_get(customer, "id")
        if not customer_id:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Stripe customer creation failed",
            )
        locked_org.stripe_customer_id = str(customer_id)
        await db.flush()
        return locked_org.stripe_customer_id

    async def create_checkout_session(
        self,
        org: Organization,
        plan: str,
        db: AsyncSession,
    ) -> str:
        self._require_stripe_enabled()
        plan_key = plan.lower().strip()
        if plan_key == "enterprise":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Enterprise plan requires manual setup",
            )
        price_id = self._price_id_for_plan(plan_key)
        if not price_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing Stripe price ID for {plan_key}",
            )

        customer_id = await self.get_or_create_customer(org, db)
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=settings.STRIPE_SUCCESS_URL,
            cancel_url=settings.STRIPE_CANCEL_URL,
            client_reference_id=str(org.id),
            metadata={"org_id": str(org.id), "target_plan": plan_key},
        )
        checkout_url = _event_get(session, "url")
        if not checkout_url:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Stripe checkout session creation failed",
            )
        return str(checkout_url)

    async def create_portal_session(self, org: Organization, db: AsyncSession) -> str:
        self._require_stripe_enabled()
        locked_org = await db.scalar(
            select(Organization).where(Organization.id == org.id).with_for_update()
        )
        if locked_org is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found",
            )
        if not locked_org.stripe_customer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization has no Stripe customer",
            )

        session = stripe.billing_portal.Session.create(
            customer=locked_org.stripe_customer_id,
            return_url=settings.STRIPE_SUCCESS_URL.rsplit("?", 1)[0],
        )
        portal_url = _event_get(session, "url")
        if not portal_url:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Stripe portal session creation failed",
            )
        return str(portal_url)

    async def _find_org_for_checkout(self, event_obj: Any, db: AsyncSession) -> Organization | None:
        org_ref = _event_get(event_obj, "client_reference_id") or _event_get(
            event_obj, "metadata", "org_id"
        )
        if not org_ref:
            return None
        try:
            org_id = uuid.UUID(str(org_ref))
        except ValueError:
            return None
        return await db.scalar(select(Organization).where(Organization.id == org_id).with_for_update())

    async def _find_org_by_customer(self, customer_id: str | None, db: AsyncSession) -> Organization | None:
        if not customer_id:
            return None
        return await db.scalar(
            select(Organization)
            .where(Organization.stripe_customer_id == str(customer_id))
            .with_for_update()
        )

    async def handle_webhook(self, payload: bytes, sig_header: str, db: AsyncSession) -> None:
        self._require_stripe_enabled()
        if not settings.STRIPE_WEBHOOK_SECRET:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stripe webhook secret is not configured",
            )
        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig_header,
                secret=settings.STRIPE_WEBHOOK_SECRET,
            )
        except (stripe.error.SignatureVerificationError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Stripe signature",
            ) from exc

        event_id = str(_event_get(event, "id", default=""))
        if not event_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Malformed Stripe event",
            )

        result = await db.execute(
            pg_insert(StripeEvent)
            .values(event_id=event_id)
            .on_conflict_do_nothing(index_elements=["event_id"])
        )
        if result.rowcount == 0:
            return

        event_type = str(_event_get(event, "type", default=""))
        event_obj = _event_get(event, "data", "object", default={})

        if event_type == "checkout.session.completed":
            if _event_get(event_obj, "payment_status") == "paid":
                org = await self._find_org_for_checkout(event_obj, db)
                if org is not None:
                    org.stripe_customer_id = _event_get(event_obj, "customer") or org.stripe_customer_id
                    org.stripe_subscription_id = _event_get(event_obj, "subscription") or org.stripe_subscription_id
                    org.stripe_subscription_status = "active"

        elif event_type == "invoice.paid":
            customer_id = _event_get(event_obj, "customer")
            org = await self._find_org_by_customer(customer_id, db)
            if org is not None:
                before_plan = org.plan
                price_id = _event_get(event_obj, "lines", "data", default=[])
                mapped_plan = None
                if isinstance(price_id, list) and price_id:
                    mapped_plan = self._plan_for_price_id(
                        _event_get(price_id[0], "price", "id")
                    )
                if mapped_plan:
                    org.plan = mapped_plan
                    await self._log_plan_change(
                        db,
                        org=org,
                        before_plan=before_plan,
                        action="billing.plan_changed",
                        event_id=event_id,
                    )
                org.stripe_subscription_status = "active"

        elif event_type == "invoice.payment_failed":
            org = await self._find_org_by_customer(_event_get(event_obj, "customer"), db)
            if org is not None:
                org.stripe_subscription_status = "past_due"

        elif event_type == "customer.subscription.updated":
            org = await self._find_org_by_customer(_event_get(event_obj, "customer"), db)
            if org is not None:
                before_plan = org.plan
                org.stripe_subscription_id = _event_get(event_obj, "id") or org.stripe_subscription_id
                org.stripe_subscription_status = _event_get(event_obj, "status") or org.stripe_subscription_status
                items = _event_get(event_obj, "items", "data", default=[])
                mapped_plan = None
                if isinstance(items, list) and items:
                    mapped_plan = self._plan_for_price_id(
                        _event_get(items[0], "price", "id")
                    )
                if mapped_plan:
                    org.plan = mapped_plan
                    await self._log_plan_change(
                        db,
                        org=org,
                        before_plan=before_plan,
                        action="billing.plan_changed",
                        event_id=event_id,
                    )

        elif event_type == "customer.subscription.deleted":
            org = await self._find_org_by_customer(_event_get(event_obj, "customer"), db)
            if org is not None:
                before_plan = org.plan
                org.plan = "free"
                org.stripe_subscription_id = None
                org.stripe_subscription_status = "canceled"
                await self._log_plan_change(
                    db,
                    org=org,
                    before_plan=before_plan,
                    action="billing.plan_changed",
                    event_id=event_id,
                )

        await db.commit()


billing_service = BillingService()
