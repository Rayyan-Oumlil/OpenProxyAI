"""Stripe billing routes: checkout, portal, and webhook receiver."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db
from app.models.organization import Organization
from app.services.billing_service import billing_service

router = APIRouter(prefix="/api/v1/billing", tags=["Billing"])


class CheckoutRequest(BaseModel):
    plan: str


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalResponse(BaseModel):
    portal_url: str


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    payload: CheckoutRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> CheckoutResponse:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    org = await db.get(Organization, current_user.org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    checkout_url = await billing_service.create_checkout_session(org, payload.plan, db)
    await db.commit()
    return CheckoutResponse(checkout_url=checkout_url)


@router.post("/portal", response_model=PortalResponse)
async def create_portal(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> PortalResponse:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    org = await db.get(Organization, current_user.org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    portal_url = await billing_service.create_portal_session(org, db)
    await db.commit()
    return PortalResponse(portal_url=portal_url)


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    await billing_service.handle_webhook(payload=payload, sig_header=signature, db=db)
    return {"received": True}
