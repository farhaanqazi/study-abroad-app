"""Admin: audit-log viewer.

READ-ONLY by design. Audit logs are append-only — this surface exposes only
search/list (no create/update/delete). Requires SUPPORT+.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.dependencies.auth import PlatformContext, PlatformRequire
from app.core.enums import PlatformRole
from app.schemas.ops import AuditLogOut
from app.services import ops as svc

router = APIRouter(prefix="/audit-logs", tags=["admin: audit"])

require_support = PlatformRequire(PlatformRole.SUPPORT)


@router.get("", response_model=list[AuditLogOut])
async def list_audit_logs(
    ctx: PlatformContext = Depends(require_support),
    db: AsyncSession = Depends(get_db),
    actor_user_id: Optional[UUID] = Query(None),
    action: Optional[str] = Query(None, description="Action prefix match."),
    vendor_id: Optional[UUID] = Query(None),
    target_type: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[AuditLogOut]:
    rows = await svc.search_audit_logs(
        db,
        actor_user_id=actor_user_id,
        action_prefix=action,
        vendor_id=vendor_id,
        target_type=target_type,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return [
        AuditLogOut(
            id=str(row.id),
            actor_user_id=str(row.actor_user_id) if row.actor_user_id else None,
            actor_role=row.actor_role,
            action=row.action,
            target_type=row.target_type,
            target_id=str(row.target_id) if row.target_id else None,
            vendor_id=str(row.vendor_id) if row.vendor_id else None,
            details=row.details or {},
            ip=row.ip,
            created_at=row.created_at,
        )
        for row in rows
    ]
