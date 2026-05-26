"""User-facing workspace requests.

Authenticated (not tenant-scoped, not admin): a user with no workspace submits
a provisioning request and polls its status. Mounted at
/api/v1/workspace-requests.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.dependencies.auth import get_current_user
from app.db.models.tenant import User
from app.schemas.workspace import WorkspaceRequestCreate, WorkspaceRequestOut
from app.services import workspace_requests as svc

router = APIRouter(prefix="/workspace-requests", tags=["workspace-requests"])


def _out(req) -> WorkspaceRequestOut:
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


@router.post("", response_model=WorkspaceRequestOut, status_code=201)
async def submit_workspace_request(
    payload: WorkspaceRequestCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceRequestOut:
    try:
        req = await svc.submit_request(
            db,
            user=user,
            business_name=payload.business_name,
            desired_slug=payload.desired_slug,
            justification=payload.justification,
        )
    except svc.WorkspaceRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return _out(req)


@router.get("/mine", response_model=list[WorkspaceRequestOut])
async def list_my_workspace_requests(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WorkspaceRequestOut]:
    rows = await svc.list_own_requests(db, user=user)
    return [_out(r) for r in rows]
