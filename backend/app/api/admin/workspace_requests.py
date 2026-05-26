"""Admin: review queue for workspace provisioning requests.

GET (list) requires SUPPORT+ (read-only operators can triage); approve/reject
require ADMIN+. Every decision is audited inside the same transaction.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.dependencies.auth import PlatformContext, PlatformRequire
from app.core.enums import PlatformRole, WorkspaceRequestStatus
from app.db.models.platform import WorkspaceRequest
from app.db.models.tenant import User
from app.schemas.workspace import (
    AdminWorkspaceRequestOut,
    ApproveWorkspaceRequestIn,
    RejectWorkspaceRequestIn,
    WorkspaceRequestOut,
)
from app.services import workspace_requests as svc

router = APIRouter(prefix="/workspace-requests", tags=["admin: workspace-requests"])

require_support = PlatformRequire(PlatformRole.SUPPORT)
require_admin = PlatformRequire(PlatformRole.ADMIN)


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _admin_out(req: WorkspaceRequest, requester_email: Optional[str]) -> AdminWorkspaceRequestOut:
    return AdminWorkspaceRequestOut(
        id=str(req.id),
        business_name=req.business_name,
        desired_slug=req.desired_slug,
        justification=req.justification,
        status=req.status.value,
        rejection_reason=req.rejection_reason,
        created_vendor_id=str(req.created_vendor_id) if req.created_vendor_id else None,
        created_at=req.created_at,
        requested_by_user_id=str(req.requested_by_user_id),
        requester_email=requester_email,
        reviewed_by_user_id=str(req.reviewed_by_user_id) if req.reviewed_by_user_id else None,
        reviewed_at=req.reviewed_at,
    )


@router.get("", response_model=list[AdminWorkspaceRequestOut])
async def list_workspace_requests(
    ctx: PlatformContext = Depends(require_support),
    db: AsyncSession = Depends(get_db),
    status: Optional[WorkspaceRequestStatus] = Query(None, description="Filter by status."),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[AdminWorkspaceRequestOut]:
    stmt = (
        select(WorkspaceRequest, User.email)
        .join(User, User.id == WorkspaceRequest.requested_by_user_id)
        .order_by(WorkspaceRequest.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status is not None:
        stmt = stmt.where(WorkspaceRequest.status == status)
    rows = (await db.execute(stmt)).all()
    return [_admin_out(req, email) for (req, email) in rows]


@router.post("/{request_id}/approve", response_model=WorkspaceRequestOut)
async def approve_workspace_request(
    request_id: UUID,
    request: Request,
    payload: ApproveWorkspaceRequestIn | None = None,
    ctx: PlatformContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceRequestOut:
    try:
        req, _vendor = await svc.approve_request(
            db,
            admin=ctx.user,
            request_id=request_id,
            slug_override=payload.slug_override if payload else None,
            ip=_client_ip(request),
        )
    except svc.WorkspaceRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return WorkspaceRequestOut(
        id=str(req.id),
        business_name=req.business_name,
        desired_slug=req.desired_slug,
        justification=req.justification,
        status=req.status.value,
        rejection_reason=req.rejection_reason,
        created_vendor_id=str(req.created_vendor_id) if req.created_vendor_id else None,
        created_at=req.created_at,
    )


@router.post("/{request_id}/reject", response_model=WorkspaceRequestOut)
async def reject_workspace_request(
    request_id: UUID,
    request: Request,
    payload: RejectWorkspaceRequestIn | None = None,
    ctx: PlatformContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceRequestOut:
    try:
        req = await svc.reject_request(
            db,
            admin=ctx.user,
            request_id=request_id,
            reason=payload.reason if payload else None,
            ip=_client_ip(request),
        )
    except svc.WorkspaceRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return WorkspaceRequestOut(
        id=str(req.id),
        business_name=req.business_name,
        desired_slug=req.desired_slug,
        justification=req.justification,
        status=req.status.value,
        rejection_reason=req.rejection_reason,
        created_vendor_id=str(req.created_vendor_id) if req.created_vendor_id else None,
        created_at=req.created_at,
    )
