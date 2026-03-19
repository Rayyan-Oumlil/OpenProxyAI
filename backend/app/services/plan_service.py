"""Plan feature gate helpers — raise HTTP 402 when a plan limit is exceeded."""

from typing import Any

from fastapi import HTTPException, status

from app.config import PLAN_FEATURES, settings
from app.models.organization import Organization


def get_plan_feature(org: Organization, feature: str) -> Any:
    """Return the feature value for the org's current plan."""
    plan = (org.plan or "free").lower()
    features = PLAN_FEATURES.get(plan, PLAN_FEATURES["free"])
    return features.get(feature)


def included_tokens_monthly_for_org(org: Organization) -> int | None:
    """Return included token quota for metered plans; None if not usage-metered.

    Uses ``METERED_INCLUDED_TOKENS_MONTHLY`` from settings for the ``metered`` tier.
    """
    plan = (org.plan or "free").lower()
    if plan != "metered":
        return None
    return int(settings.METERED_INCLUDED_TOKENS_MONTHLY)


def assert_plan_allows(org: Organization, feature: str) -> None:
    """Raise HTTP 402 if the feature is disabled on the org's plan."""
    value = get_plan_feature(org, feature)
    if value is False:
        plan = (org.plan or "free").lower()
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "plan_limit_exceeded",
                "feature": feature,
                "plan": plan,
                "detail": f"Upgrade your plan to enable '{feature}'.",
            },
        )


def check_user_limit(org: Organization, current_count: int) -> None:
    """Raise HTTP 402 if adding one more user would exceed the plan max."""
    max_users = get_plan_feature(org, "max_users")
    if max_users != -1 and current_count >= max_users:
        plan = (org.plan or "free").lower()
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "plan_limit_exceeded",
                "feature": "max_users",
                "plan": plan,
                "detail": f"Upgrade to add more than {max_users} users.",
            },
        )


def check_api_key_limit(org: Organization, current_count: int) -> None:
    """Raise HTTP 402 if adding one more API key would exceed the plan max."""
    max_keys = get_plan_feature(org, "max_api_keys")
    if max_keys != -1 and current_count >= max_keys:
        plan = (org.plan or "free").lower()
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "plan_limit_exceeded",
                "feature": "max_api_keys",
                "plan": plan,
                "detail": f"Upgrade to create more than {max_keys} API keys.",
            },
        )
