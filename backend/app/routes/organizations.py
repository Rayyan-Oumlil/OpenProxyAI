"""Organization settings endpoints."""

import dataclasses
import math
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db, get_redis
from app.models.organization import Organization
from app.models.webhook_delivery import WebhookDelivery
from app.schemas.logs import Page
from app.schemas.organization import OrganizationResponse, OrganizationUpdateRequest
from app.schemas.policy import ApplyTemplateRequest, PolicyConfigRequest, PolicyConfigResponse, TemplateListItem
from app.schemas.webhook import (
    WebhookConfigRequest,
    WebhookConfigResponse,
    WebhookDeliveryDetailResponse,
    WebhookDeliveryResponse,
)
from app.services.admin_audit_service import (
    get_ip,
    log_admin_action,
    serialize_org,
    serialize_webhook_config,
)
from app.services.compliance_templates import get_template, list_templates
from app.services.plan_service import assert_plan_allows, included_tokens_monthly_for_org
from app.services.policy_service import PolicyConfig, _POLICY_CACHE_KEY, policy_store
from app.services.webhook_service import _deliver

def _policy_response(config: PolicyConfig) -> PolicyConfigResponse:
	return PolicyConfigResponse(**dataclasses.asdict(config))


router = APIRouter(prefix="/api/v1/organizations", tags=["Organizations"])


@router.get("/current", response_model=OrganizationResponse)
async def get_current_organization(
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
	model = await db.scalar(select(Organization).where(Organization.id == current_user.org_id))
	if model is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
	return _organization_to_response(model)


def _organization_to_response(model: Organization) -> OrganizationResponse:
	base = OrganizationResponse.model_validate(model)
	safe_settings = _sanitize_settings_for_response(dict(base.settings))
	quota = included_tokens_monthly_for_org(model)
	return base.model_copy(update={"settings": safe_settings, "included_tokens_monthly": quota})


# Keys only Stripe webhooks / billing may write; clients must not set via PATCH.
_SERVER_MANAGED_SETTINGS_KEYS = frozenset({"stripe_metered_subscription_item_id"})


def _sanitize_settings_for_response(settings: dict) -> dict:
	"""Strip secrets and server-managed billing cache from the settings dict."""
	safe = {
		k: v
		for k, v in settings.items()
		if k not in _SERVER_MANAGED_SETTINGS_KEYS
	}
	webhooks = safe.get("webhooks")
	if isinstance(webhooks, dict):
		safe["webhooks"] = {k: v for k, v in webhooks.items() if k != "secret"}
	return safe


@router.patch("/current", response_model=OrganizationResponse)
async def update_current_organization(
	payload: OrganizationUpdateRequest,
	request: Request,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
	if current_user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

	model = await db.scalar(select(Organization).where(Organization.id == current_user.org_id))
	if model is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

	updates = payload.model_dump(exclude_unset=True)
	if updates.get("is_active") is False:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Organization deactivation is not allowed from this endpoint",
		)
	if "plan" in updates:
		if model.stripe_subscription_id is not None:
			raise HTTPException(
				status_code=status.HTTP_409_CONFLICT,
				detail="Plan is managed by Stripe. Use the billing portal to change plans.",
			)
		allowed_manual_plans = {"free", "starter"}
		if updates["plan"] not in allowed_manual_plans:
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail=f"Plan '{updates['plan']}' requires a Stripe subscription.",
			)

	before = serialize_org(model)

	settings_patch = updates.pop("settings", None)

	for field_name, field_value in updates.items():
		setattr(model, field_name, field_value)

	_RESERVED_SETTINGS_KEYS = {"webhooks", "policy", *_SERVER_MANAGED_SETTINGS_KEYS}

	if settings_patch is not None:
		for reserved_key in _RESERVED_SETTINGS_KEYS:
			if reserved_key in settings_patch:
				raise HTTPException(
					status_code=status.HTTP_400_BAD_REQUEST,
					detail=f"Cannot set '{reserved_key}' via this endpoint. Use the dedicated /{reserved_key} endpoint.",
				)
		merged_settings = dict(model.settings or {})
		merged_settings.update(settings_patch)
		model.settings = merged_settings

	after = serialize_org(model)

	await log_admin_action(
		db,
		org_id=current_user.org_id,
		actor_id=current_user.id,
		actor_email=current_user.email,
		action="organization.updated",
		resource_type="organization",
		resource_id=str(current_user.org_id),
		before=before,
		after=after,
		ip_address=get_ip(request),
	)

	await db.commit()
	await db.refresh(model)
	return _organization_to_response(model)


@router.get("/current/policy", response_model=PolicyConfigResponse)
async def get_policy_config(
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
	redis: Redis = Depends(get_redis),
) -> PolicyConfigResponse:
	"""Return the current policy configuration for the organization."""
	config = await policy_store.load(current_user.org_id, db, redis)
	return _policy_response(config)


@router.patch("/current/policy", response_model=PolicyConfigResponse)
async def update_policy_config(
	payload: PolicyConfigRequest,
	request: Request,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
	redis: Redis = Depends(get_redis),
) -> PolicyConfigResponse:
	"""Merge-update the policy configuration for the organization.

	Only provided fields are changed; omitted fields keep their current value.
	Changes take effect within 60 seconds (Redis cache TTL).
	"""
	if current_user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

	updates = payload.model_dump(exclude_unset=True)

	# Enforce plan gate: pii_detection requires a plan that supports it
	if updates.get("pii_detection_enabled") is True:
		org = await db.get(Organization, current_user.org_id)
		assert_plan_allows(org, "pii_detection")

	current = await policy_store.load(current_user.org_id, db, redis)
	before_data = current.to_dict()

	# replace() keeps every field the request did not mention, including ones added later.
	new_config = dataclasses.replace(current, **updates, updated_at=datetime.now(UTC))

	await log_admin_action(
		db,
		org_id=current_user.org_id,
		actor_id=current_user.id,
		actor_email=current_user.email,
		action="policy.updated",
		resource_type="policy",
		resource_id=str(current_user.org_id),
		before=before_data,
		after=new_config.to_dict(),
		ip_address=get_ip(request),
	)

	await policy_store.save(current_user.org_id, new_config, db, redis)

	return _policy_response(new_config)


@router.get("/current/policy/templates", response_model=list[TemplateListItem])
async def list_policy_templates(
	current_user: CurrentUser,
) -> list[TemplateListItem]:
	"""Return available compliance templates (no DB query)."""
	return [TemplateListItem.model_validate(t) for t in list_templates()]


@router.post("/current/policy/apply-template", response_model=PolicyConfigResponse)
async def apply_policy_template(
	payload: ApplyTemplateRequest,
	request: Request,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
	redis: Redis = Depends(get_redis),
) -> PolicyConfigResponse:
	"""Apply a compliance template to the org policy. Merges with existing; preserves allowed_models and model_rate_limits."""
	if current_user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

	template_def = get_template(payload.template)
	if template_def is None:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=f"Unknown template: {payload.template}",
		)

	org = await db.scalar(select(Organization).where(Organization.id == current_user.org_id))
	if org is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

	assert_plan_allows(org, "pii_detection")

	current = await policy_store.load(current_user.org_id, db, redis)

	# The template owns the guardrail fields; everything else (model allowlist, rate limits,
	# MCP tool policy, fields added later) is kept from the current config.
	merged_config = dataclasses.replace(
		current,
		enforcement_mode=template_def.enforcement_mode,
		blocked_keywords=list(template_def.blocked_keywords),
		pii_detection_enabled=template_def.pii_detection_enabled,
		pii_entities=list(template_def.pii_entities),
		prompt_injection_detection_enabled=template_def.prompt_injection_detection_enabled,
		response_guardrails_enabled=template_def.response_guardrails_enabled,
		response_pii_redact=template_def.response_pii_redact,
		updated_at=datetime.now(UTC),
	)

	policy_dict = merged_config.to_dict()
	policy_dict["metadata"] = {
		"template": template_def.metadata.template,
		"template_version": template_def.metadata.template_version,
		"audit_retention_days": template_def.metadata.audit_retention_days,
	}

	merged_settings = dict(org.settings or {})
	merged_settings["policy"] = policy_dict
	org.settings = merged_settings

	await log_admin_action(
		db,
		org_id=current_user.org_id,
		actor_id=current_user.id,
		actor_email=current_user.email,
		action="apply_compliance_template",
		resource_type="policy",
		resource_id=str(current_user.org_id),
		before=current.to_dict(),
		after={"template": payload.template},
		ip_address=get_ip(request),
	)

	await db.commit()
	await db.refresh(org)

	cache_key = _POLICY_CACHE_KEY.format(org_id=current_user.org_id)
	await redis.delete(cache_key)

	return _policy_response(merged_config)


@router.get("/current/webhooks", response_model=WebhookConfigResponse)
async def get_webhook_config(
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> WebhookConfigResponse:
	"""Return the webhook configuration for the current organization."""
	if current_user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
	org = await db.get(Organization, current_user.org_id)
	if org is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
	cfg = (org.settings or {}).get("webhooks", {})
	return WebhookConfigResponse(
		url=cfg.get("url", ""),
		events=cfg.get("events", ["policy.violation", "budget.alert"]),
		enabled=cfg.get("enabled", False),
	)


@router.patch("/current/webhooks", response_model=WebhookConfigResponse)
async def update_webhook_config(
	payload: WebhookConfigRequest,
	request: Request,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> WebhookConfigResponse:
	"""Update the webhook configuration for the current organization."""
	if current_user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
	org = await db.get(Organization, current_user.org_id)
	if org is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

	before = serialize_webhook_config((org.settings or {}).get("webhooks", {}))

	new_settings = dict(org.settings or {})
	new_settings["webhooks"] = {
		"url": payload.url,
		"secret": payload.secret,
		"events": payload.events,
		"enabled": payload.enabled,
	}
	org.settings = new_settings

	after = serialize_webhook_config(new_settings["webhooks"])

	await log_admin_action(
		db,
		org_id=current_user.org_id,
		actor_id=current_user.id,
		actor_email=current_user.email,
		action="webhook.updated",
		resource_type="webhook",
		resource_id=str(current_user.org_id),
		before=before,
		after=after,
		ip_address=get_ip(request),
	)

	await db.commit()
	return WebhookConfigResponse(
		url=payload.url,
		events=payload.events,
		enabled=payload.enabled,
	)


@router.get("/current/webhooks/deliveries", response_model=Page[WebhookDeliveryResponse])
async def list_webhook_deliveries(
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
	page: int = Query(1, ge=1),
	page_size: int = Query(20, ge=1, le=100),
	delivery_status: str | None = Query(None, alias="status"),
) -> Page[WebhookDeliveryResponse]:
	"""Paginated list of webhook delivery attempts for the org."""
	if current_user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")

	base = select(WebhookDelivery).where(WebhookDelivery.org_id == current_user.org_id)
	count_q = select(func.count()).select_from(WebhookDelivery).where(WebhookDelivery.org_id == current_user.org_id)

	if delivery_status is not None:
		base = base.where(WebhookDelivery.status == delivery_status)
		count_q = count_q.where(WebhookDelivery.status == delivery_status)

	total = (await db.execute(count_q)).scalar_one()
	rows = (
		await db.scalars(
			base.order_by(WebhookDelivery.created_at.desc())
			.offset((page - 1) * page_size)
			.limit(page_size)
		)
	).all()

	return Page[WebhookDeliveryResponse](
		items=[WebhookDeliveryResponse.model_validate(r) for r in rows],
		total=total,
		page=page,
		page_size=page_size,
		total_pages=max(1, math.ceil(total / page_size)),
	)


@router.post(
	"/current/webhooks/deliveries/{delivery_id}/retry",
	response_model=WebhookDeliveryDetailResponse,
)
async def retry_webhook_delivery(
	delivery_id: uuid.UUID,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> WebhookDeliveryDetailResponse:
	"""Manually retry a failed webhook delivery."""
	if current_user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")

	delivery = await db.scalar(
		select(WebhookDelivery).where(
			WebhookDelivery.id == delivery_id,
			WebhookDelivery.org_id == current_user.org_id,
		)
	)
	if delivery is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found")

	if delivery.status == "delivered":
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail="Delivery already succeeded — nothing to retry",
		)

	org = await db.get(Organization, current_user.org_id)
	if org is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
	secret = ((org.settings or {}).get("webhooks", {})).get("secret", "")

	new_status, http_status = await _deliver(delivery.url, delivery.payload, secret)
	if new_status == "failed" and http_status is None:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Webhook URL is no longer considered safe",
		)
	delivery.status = new_status
	delivery.http_status = http_status
	delivery.attempt_count += 1
	delivery.last_attempted_at = datetime.now(UTC)
	await db.commit()
	await db.refresh(delivery)

	return WebhookDeliveryDetailResponse.model_validate(delivery)
