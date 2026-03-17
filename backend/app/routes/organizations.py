"""Organization settings endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db, get_redis
from app.models.organization import Organization
from app.schemas.organization import OrganizationResponse, OrganizationUpdateRequest
from app.schemas.policy import PolicyConfigRequest, PolicyConfigResponse
from app.schemas.webhook import WebhookConfigRequest, WebhookConfigResponse
from app.services.plan_service import assert_plan_allows
from app.services.policy_service import PolicyConfig, policy_store

router = APIRouter(prefix="/api/v1/organizations", tags=["Organizations"])


@router.get("/current", response_model=OrganizationResponse)
async def get_current_organization(
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
	model = await db.scalar(select(Organization).where(Organization.id == current_user.org_id))
	if model is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
	return OrganizationResponse.model_validate(model)


@router.patch("/current", response_model=OrganizationResponse)
async def update_current_organization(
	payload: OrganizationUpdateRequest,
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

	settings_patch = updates.pop("settings", None)

	for field_name, field_value in updates.items():
		setattr(model, field_name, field_value)

	if settings_patch is not None:
		merged_settings = dict(model.settings or {})
		merged_settings.update(settings_patch)
		model.settings = merged_settings

	await db.commit()
	await db.refresh(model)
	return OrganizationResponse.model_validate(model)


@router.get("/current/policy", response_model=PolicyConfigResponse)
async def get_policy_config(
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
	redis: Redis = Depends(get_redis),
) -> PolicyConfigResponse:
	"""Return the current policy configuration for the organization."""
	config = await policy_store.load(current_user.org_id, db, redis)
	return PolicyConfigResponse(
		enforcement_mode=config.enforcement_mode,
		allowed_models=config.allowed_models,
		blocked_keywords=config.blocked_keywords,
		pii_detection_enabled=config.pii_detection_enabled,
		pii_entities=config.pii_entities,
		model_rate_limits=config.model_rate_limits,
		updated_at=config.updated_at,
		prompt_injection_detection_enabled=config.prompt_injection_detection_enabled,
		response_guardrails_enabled=config.response_guardrails_enabled,
		response_pii_redact=config.response_pii_redact,
	)


@router.patch("/current/policy", response_model=PolicyConfigResponse)
async def update_policy_config(
	payload: PolicyConfigRequest,
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

	new_config = PolicyConfig(
		enforcement_mode=updates.get("enforcement_mode", current.enforcement_mode),
		allowed_models=updates.get("allowed_models", current.allowed_models),
		blocked_keywords=updates.get("blocked_keywords", current.blocked_keywords),
		pii_detection_enabled=updates.get("pii_detection_enabled", current.pii_detection_enabled),
		pii_entities=updates.get("pii_entities", current.pii_entities),
		model_rate_limits=updates.get("model_rate_limits", current.model_rate_limits),
		prompt_injection_detection_enabled=updates.get("prompt_injection_detection_enabled", current.prompt_injection_detection_enabled),
		response_guardrails_enabled=updates.get("response_guardrails_enabled", current.response_guardrails_enabled),
		response_pii_redact=updates.get("response_pii_redact", current.response_pii_redact),
		updated_at=datetime.now(UTC),
	)

	await policy_store.save(current_user.org_id, new_config, db, redis)

	return PolicyConfigResponse(
		enforcement_mode=new_config.enforcement_mode,
		allowed_models=new_config.allowed_models,
		blocked_keywords=new_config.blocked_keywords,
		pii_detection_enabled=new_config.pii_detection_enabled,
		pii_entities=new_config.pii_entities,
		model_rate_limits=new_config.model_rate_limits,
		updated_at=new_config.updated_at,
		prompt_injection_detection_enabled=new_config.prompt_injection_detection_enabled,
		response_guardrails_enabled=new_config.response_guardrails_enabled,
		response_pii_redact=new_config.response_pii_redact,
	)


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
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
) -> WebhookConfigResponse:
	"""Update the webhook configuration for the current organization."""
	if current_user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
	org = await db.get(Organization, current_user.org_id)
	if org is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
	new_settings = dict(org.settings or {})
	new_settings["webhooks"] = {
		"url": payload.url,
		"secret": payload.secret,
		"events": payload.events,
		"enabled": payload.enabled,
	}
	org.settings = new_settings
	await db.commit()
	return WebhookConfigResponse(
		url=payload.url,
		events=payload.events,
		enabled=payload.enabled,
	)
