"""Admin audit log endpoint — paginated list scoped by org, admin-only."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, get_db
from app.models.admin_audit_log import AdminAuditLog
from app.schemas.admin_audit import AdminAuditLogResponse
from app.schemas.logs import Page

router = APIRouter(prefix="/api/v1/admin/audit-log", tags=["Admin Audit"])


@router.get("", response_model=Page[AdminAuditLogResponse])
async def list_audit_log(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
) -> Page[AdminAuditLogResponse]:
    """Return a paginated list of admin audit log entries for the caller's org.

    Requires admin role. Filtered by action and/or resource_type when supplied.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required to access audit log",
        )

    filters = [AdminAuditLog.org_id == current_user.org_id]
    if action:
        filters.append(AdminAuditLog.action == action)
    if resource_type:
        filters.append(AdminAuditLog.resource_type == resource_type)

    total = await db.scalar(
        select(func.count()).select_from(AdminAuditLog).where(*filters)
    )
    rows = await db.scalars(
        select(AdminAuditLog)
        .where(*filters)
        .order_by(AdminAuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    items = [
        AdminAuditLogResponse(
            id=str(r.id),
            actor_email=r.actor_email,
            action=r.action,
            resource_type=r.resource_type,
            resource_id=r.resource_id,
            before=r.before,
            after=r.after,
            ip_address=r.ip_address,
            created_at=r.created_at.isoformat(),
        )
        for r in rows.all()
    ]

    safe_total = total or 0
    return Page(
        items=items,
        total=safe_total,
        page=page,
        page_size=page_size,
        total_pages=(safe_total + page_size - 1) // page_size,
    )
