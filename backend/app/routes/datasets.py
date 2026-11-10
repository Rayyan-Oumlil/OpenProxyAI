"""Admin API for evaluation datasets: /api/v1/datasets (admins only). Phase 3, slice 3.

Datasets hold copies of prompts, so everything here is admin-only and recorded in the admin audit log.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db
from app.models.dataset import Dataset, DatasetItem
from app.schemas.dataset import (
	MAX_ITEMS_PER_DATASET,
	DatasetCreate,
	DatasetResponse,
	ImportRequest,
	ImportResponse,
	ItemCreate,
	ItemResponse,
)
from app.services.admin_audit_service import get_ip, log_admin_action
from app.services.dataset_service import import_from_payloads, item_count, pii_kinds

router = APIRouter(prefix="/api/v1/datasets", tags=["Datasets"])

_ADMIN_ONLY = "Only organization admins can manage datasets"


def _require_admin(user) -> None:
	if user.role != "admin":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)


async def _load(db: AsyncSession, org_id: UUID, dataset_id: UUID) -> Dataset:
	dataset = await db.get(Dataset, dataset_id)
	if dataset is None or dataset.org_id != org_id:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
	return dataset


def _response(dataset: Dataset, count: int) -> DatasetResponse:
	return DatasetResponse(id=dataset.id, name=dataset.name, description=dataset.description, item_count=count, created_at=dataset.created_at)


async def _audit(db, user, request: Request, action: str, dataset: Dataset, after: dict | None = None) -> None:
	await log_admin_action(
		db, org_id=user.org_id, actor_id=user.id, actor_email=user.email, action=action,
		resource_type="dataset", resource_id=str(dataset.id), after={"name": dataset.name, **(after or {})}, ip_address=get_ip(request),
	)


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset(payload: DatasetCreate, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> DatasetResponse:
	_require_admin(current_user)
	dataset = Dataset(org_id=current_user.org_id, name=payload.name, description=payload.description, created_by=current_user.id)
	db.add(dataset)
	try:
		await db.flush()
	except IntegrityError:
		await db.rollback()
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error": "dataset_exists", "detail": "A dataset with this name already exists."}) from None
	await _audit(db, current_user, request, "dataset.created", dataset)
	await db.commit()
	await db.refresh(dataset)
	return _response(dataset, 0)


@router.get("", response_model=list[DatasetResponse])
async def list_datasets(current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> list[DatasetResponse]:
	_require_admin(current_user)
	counts = select(DatasetItem.dataset_id, func.count().label("n")).group_by(DatasetItem.dataset_id).subquery()
	rows = await db.execute(
		select(Dataset, func.coalesce(counts.c.n, 0))
		.outerjoin(counts, counts.c.dataset_id == Dataset.id)
		.where(Dataset.org_id == current_user.org_id)
		.order_by(Dataset.name)
	)
	return [_response(dataset, int(n)) for dataset, n in rows.all()]


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(dataset_id: UUID, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> DatasetResponse:
	_require_admin(current_user)
	dataset = await _load(db, current_user.org_id, dataset_id)
	return _response(dataset, await item_count(db, dataset.id))


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(dataset_id: UUID, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> Response:
	_require_admin(current_user)
	dataset = await _load(db, current_user.org_id, dataset_id)
	count = await item_count(db, dataset.id)
	await _audit(db, current_user, request, "dataset.deleted", dataset, {"items": count})
	await db.delete(dataset)
	await db.commit()
	return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{dataset_id}/import", response_model=ImportResponse)
async def import_items(
	dataset_id: UUID, payload: ImportRequest, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> ImportResponse:
	"""Copy captured requests into the dataset. Rows with PII are skipped, repeats are skipped, the count is capped."""
	_require_admin(current_user)
	dataset = await _load(db, current_user.org_id, dataset_id)
	result = await import_from_payloads(db, current_user.org_id, dataset.id, payload)
	await _audit(db, current_user, request, "dataset.imported", dataset, result.model_dump())
	await db.commit()
	return result


@router.post("/{dataset_id}/items", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def add_item(dataset_id: UUID, payload: ItemCreate, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> ItemResponse:
	"""Add one prompt by hand. PII is refused, not silently rewritten: changing an expected answer would quietly change what a test checks."""
	_require_admin(current_user)
	dataset = await _load(db, current_user.org_id, dataset_id)
	found = pii_kinds(payload.expected, *(m.content for m in payload.messages))
	if found:
		raise HTTPException(
			status_code=422,
			detail={"error": "pii_in_item", "detail": f"This item contains personal data ({', '.join(found)}). Remove or replace it; datasets never hold PII."},
		)
	if await item_count(db, dataset.id) >= MAX_ITEMS_PER_DATASET:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error": "dataset_full", "detail": f"A dataset holds at most {MAX_ITEMS_PER_DATASET} items."})
	item = DatasetItem(
		org_id=current_user.org_id, dataset_id=dataset.id,
		messages=[{"role": m.role, "content": m.content} for m in payload.messages], expected=payload.expected,
	)
	db.add(item)
	await db.commit()
	await db.refresh(item)
	return ItemResponse.model_validate(item, from_attributes=True)


@router.get("/{dataset_id}/items", response_model=list[ItemResponse])
async def list_items(
	dataset_id: UUID,
	current_user: CurrentUser,
	db: AsyncSession = Depends(get_db),
	limit: int = Query(default=50, ge=1, le=200),
	offset: int = Query(default=0, ge=0),
) -> list[ItemResponse]:
	_require_admin(current_user)
	dataset = await _load(db, current_user.org_id, dataset_id)
	rows = await db.scalars(
		select(DatasetItem).where(DatasetItem.dataset_id == dataset.id).order_by(DatasetItem.created_at, DatasetItem.id).limit(limit).offset(offset)
	)
	return [ItemResponse.model_validate(r, from_attributes=True) for r in rows.all()]


@router.delete("/{dataset_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(dataset_id: UUID, item_id: UUID, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> Response:
	_require_admin(current_user)
	dataset = await _load(db, current_user.org_id, dataset_id)
	item = await db.get(DatasetItem, item_id)
	if item is None or item.dataset_id != dataset.id:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
	await db.delete(item)
	await db.commit()
	return Response(status_code=status.HTTP_204_NO_CONTENT)
