"""POST /api/v1/analytics/query: a structured, read-only query over the org's own logs and scores (Phase 5, slice 5.9).

Admins only, and every query is written to the admin audit log (the spec, never the rows). It runs in a read-only transaction with a short
statement timeout, limited to the caller's org twice over (an explicit filter and row-level security).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db
from app.services.admin_audit_service import get_ip, log_admin_action
from app.services.query_builder import AGGREGATES, OPERATORS, VIEWS, QueryError, QuerySpec, compile_query

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])

STATEMENT_TIMEOUT_MS = 5_000


class QueryResult(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool  # the limit was reached, so there may be more


class ViewInfo(BaseModel):
    name: str
    columns: dict[str, str]  # column -> kind


class QueryCatalog(BaseModel):
    views: list[ViewInfo]
    aggregates: list[str]
    operators: list[str]


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


@router.get("/query/catalog", response_model=QueryCatalog)
async def query_catalog(current_user: CurrentUser) -> QueryCatalog:
    """What can be queried, so a client can build the form from it instead of guessing."""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only organization admins can query analytics")
    return QueryCatalog(
        views=[ViewInfo(name=v.name, columns={name: kind for name, (_, kind) in v.columns.items()}) for v in VIEWS.values()],
        aggregates=list(AGGREGATES), operators=list(OPERATORS),
    )


@router.post("/query", response_model=QueryResult)
async def run_query(spec: QuerySpec, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> QueryResult:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only organization admins can query analytics")
    try:
        query, columns = compile_query(spec, current_user.org_id)
    except QueryError as exc:
        raise HTTPException(status_code=422, detail={"error": "invalid_query", "detail": str(exc)}) from None

    await log_admin_action(
        db, org_id=current_user.org_id, actor_id=current_user.id, actor_email=current_user.email, action="analytics.queried",
        resource_type="analytics_query", resource_id=spec.view, after={"spec": spec.model_dump(mode="json", by_alias=True)}, ip_address=get_ip(request),
    )
    await db.commit()  # the audit entry is kept even if the query then fails or times out

    # A new transaction: read-only, and the statement is cut off if it runs long. Both are LOCAL, so they end with the transaction.
    await db.execute(text("SET LOCAL transaction_read_only = on"))
    await db.execute(text(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_MS}"))
    try:
        rows = (await db.execute(query)).all()
    except DBAPIError as exc:
        await db.rollback()
        if "statement timeout" in str(exc.orig).lower():
            raise HTTPException(status_code=408, detail={"error": "query_timeout", "detail": "The query took too long. Narrow the time window or add filters."}) from None
        raise
    finally:
        await db.rollback()  # nothing was written; end the read-only transaction
    return QueryResult(columns=columns, rows=[[_json_safe(v) for v in row] for row in rows], row_count=len(rows), truncated=len(rows) >= spec.limit)
