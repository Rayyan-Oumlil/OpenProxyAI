"""An organization's data region: the one place that decides what "no region set" means."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization

DEFAULT_DATA_REGION = "us"


def region_of(org: Organization | None) -> str:
	"""The org's data region, lower-cased; ``us`` when the org is missing or has none."""
	region = getattr(org, "data_region", None)
	return region.strip().lower() if isinstance(region, str) and region.strip() else DEFAULT_DATA_REGION


async def org_data_region(db: AsyncSession, org_id: UUID | str) -> str:
	return region_of(await db.get(Organization, org_id if isinstance(org_id, UUID) else UUID(str(org_id))))
