"""Admin: platform-user (operator) management.

Listing requires ADMIN+. Granting/revoking platform roles is SUPERADMIN-only.
Anti-lockout guards (no self-demote, never demote the last superadmin) live in
the service layer and surface as 409.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.dependencies.auth import PlatformContext, PlatformRequire
from app.core.enums import PlatformRole
from app.schemas.admin import PlatformRoleUpdate, PlatformUserOut
from app.services import platform_users as svc

router = APIRouter(prefix="/users", tags=["admin: users"])

require_admin = PlatformRequire(PlatformRole.ADMIN)
require_superadmin = PlatformRequire(PlatformRole.SUPERADMIN)


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.get("", response_model=list[PlatformUserOut])
async def list_users(
    ctx: PlatformContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    q: Optional[str] = Query(None, description="Search by email."),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[PlatformUserOut]:
    rows = await svc.list_users(db, q=q, limit=limit, offset=offset)
    return [
        PlatformUserOut(
            id=str(u.id),
            email=u.email,
            platform_role=u.platform_role,
            membership_count=count,
        )
        for (u, count) in rows
    ]


@router.patch("/{user_id}/platform-role", response_model=PlatformUserOut)
async def set_platform_role(
    user_id: UUID,
    payload: PlatformRoleUpdate,
    request: Request,
    ctx: PlatformContext = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> PlatformUserOut:
    try:
        user = await svc.set_platform_role(
            db,
            actor=ctx.user,
            user_id=user_id,
            new_role=payload.platform_role,
            ip=_client_ip(request),
        )
    except svc.PlatformUserError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    # membership_count not needed for the mutation response; report 0-safe via reload.
    rows = await svc.list_users(db, q=user.email)
    count = next((c for (u, c) in rows if u.id == user.id), 0)
    return PlatformUserOut(
        id=str(user.id),
        email=user.email,
        platform_role=user.platform_role,
        membership_count=count,
    )
