"""Admin: READ-ONLY "view-as" troubleshooting.

These endpoints let an operator SEE a tenant's data to diagnose issues. They
are strictly read-only: there is NO act-as-tenant / write path, and the tenant's
auth token is NEVER issued or returned — this is pure server-side reads under
the operator's own identity. Every access writes an ``impersonation.view`` audit
row (in :mod:`app.services.ops`). Requires SUPPORT+.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.dependencies.auth import PlatformContext, PlatformRequire
from app.core.enums import PlatformRole
from app.schemas.ops import (
    ViewAsLeadOut,
    ViewAsLeadsOut,
    ViewAsSiteConfigOut,
)
from app.services import ops as svc

router = APIRouter(prefix="/vendors/{vendor_id}/view-as", tags=["admin: view-as"])

require_support = PlatformRequire(PlatformRole.SUPPORT)


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.get("/leads", response_model=ViewAsLeadsOut)
async def view_as_leads(
    vendor_id: UUID,
    request: Request,
    ctx: PlatformContext = Depends(require_support),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
) -> ViewAsLeadsOut:
    try:
        leads = await svc.view_as_leads(
            db,
            operator=ctx.user,
            vendor_id=vendor_id,
            limit=limit,
            ip=_client_ip(request),
        )
    except svc.OpsError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return ViewAsLeadsOut(
        vendor_id=str(vendor_id),
        leads=[ViewAsLeadOut(**lead) for lead in leads],
    )


@router.get("/site-config", response_model=ViewAsSiteConfigOut)
async def view_as_site_config(
    vendor_id: UUID,
    request: Request,
    ctx: PlatformContext = Depends(require_support),
    db: AsyncSession = Depends(get_db),
) -> ViewAsSiteConfigOut:
    try:
        config = await svc.view_as_site_config(
            db, operator=ctx.user, vendor_id=vendor_id, ip=_client_ip(request)
        )
    except svc.OpsError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return ViewAsSiteConfigOut(
        vendor_id=str(config.vendor_id),
        version=config.version,
        config=config.config or {},
        draft_config=config.draft_config,
        updated_at=config.updated_at,
    )
