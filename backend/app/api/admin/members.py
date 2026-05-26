"""Admin: vendor membership + invitation management.

List requires SUPPORT+; mutations require ADMIN+. The last-owner guard (a vendor
must always keep >= 1 owner) is enforced in the service layer and surfaced as
409 here. Invitation tokens are returned ONLY on creation.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.dependencies.auth import PlatformContext, PlatformRequire
from app.core.enums import PlatformRole
from app.schemas.admin import (
    InviteCreate,
    InviteResultOut,
    MemberOut,
    MemberRoleUpdate,
)
from app.services import members as svc

router = APIRouter(prefix="/vendors/{vendor_id}/members", tags=["admin: members"])

require_support = PlatformRequire(PlatformRole.SUPPORT)
require_admin = PlatformRequire(PlatformRole.ADMIN)


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.get("", response_model=list[MemberOut])
async def list_members(
    vendor_id: UUID,
    ctx: PlatformContext = Depends(require_support),
    db: AsyncSession = Depends(get_db),
) -> list[MemberOut]:
    try:
        rows = await svc.list_members(db, vendor_id=vendor_id)
    except svc.MemberAdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return [
        MemberOut(
            user_id=str(u.id),
            email=u.email,
            role=m.role,
            membership_id=str(m.id),
        )
        for (m, u) in rows
    ]


@router.post("/invite", response_model=InviteResultOut, status_code=201)
async def invite_member(
    vendor_id: UUID,
    payload: InviteCreate,
    request: Request,
    ctx: PlatformContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> InviteResultOut:
    try:
        result = await svc.invite_member(
            db,
            admin=ctx.user,
            vendor_id=vendor_id,
            email=str(payload.email),
            role=payload.role,
            ip=_client_ip(request),
        )
    except svc.MemberAdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return InviteResultOut(**result)


@router.patch("/{user_id}", response_model=MemberOut)
async def change_member_role(
    vendor_id: UUID,
    user_id: UUID,
    payload: MemberRoleUpdate,
    request: Request,
    ctx: PlatformContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> MemberOut:
    try:
        membership = await svc.change_role(
            db,
            admin=ctx.user,
            vendor_id=vendor_id,
            user_id=user_id,
            role=payload.role,
            ip=_client_ip(request),
        )
    except svc.MemberAdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    # Re-fetch email for the response.
    rows = await svc.list_members(db, vendor_id=vendor_id)
    email = next((u.email for (m, u) in rows if u.id == user_id), "")
    return MemberOut(
        user_id=str(user_id),
        email=email,
        role=membership.role,
        membership_id=str(membership.id),
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    vendor_id: UUID,
    user_id: UUID,
    request: Request,
    ctx: PlatformContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        await svc.remove_member(
            db,
            admin=ctx.user,
            vendor_id=vendor_id,
            user_id=user_id,
            ip=_client_ip(request),
        )
    except svc.MemberAdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
