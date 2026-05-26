"""Admin: platform troubleshooting / ops endpoints.

Health + overview are read-only (SUPPORT+); the outbox retry is a mutation
(ADMIN+) and audited. Routes only validate → authorize → delegate → serialize;
all logic lives in :mod:`app.services.ops`.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.dependencies.auth import PlatformContext, PlatformRequire
from app.core.enums import PlatformRole
from app.schemas.ops import (
    LeadCountsOut,
    OutboxCountsOut,
    OutboxEventOut,
    PlatformOverviewOut,
    VendorHealthOut,
    VendorStatusCountsOut,
)
from app.services import ops as svc

router = APIRouter(prefix="", tags=["admin: ops"])

require_support = PlatformRequire(PlatformRole.SUPPORT)
require_admin = PlatformRequire(PlatformRole.ADMIN)


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.get("/vendors/{vendor_id}/health", response_model=VendorHealthOut)
async def vendor_health(
    vendor_id: UUID,
    ctx: PlatformContext = Depends(require_support),
    db: AsyncSession = Depends(get_db),
) -> VendorHealthOut:
    try:
        data = await svc.vendor_health(db, vendor_id=vendor_id)
    except svc.OpsError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return VendorHealthOut(
        vendor_id=data["vendor_id"],
        slug=data["slug"],
        business_name=data["business_name"],
        status=data["status"],
        is_active=data["is_active"],
        lead_counts=LeadCountsOut(**data["lead_counts"]),
        most_recent_lead_at=data["most_recent_lead_at"],
        outbox_counts=OutboxCountsOut(**data["outbox_counts"]),
        oldest_pending_outbox_at=data["oldest_pending_outbox_at"],
        oldest_pending_outbox_age_seconds=data["oldest_pending_outbox_age_seconds"],
    )


@router.post("/outbox/{event_id}/retry", response_model=OutboxEventOut)
async def retry_outbox_event(
    event_id: UUID,
    request: Request,
    ctx: PlatformContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> OutboxEventOut:
    try:
        event = await svc.retry_outbox_event(
            db, admin=ctx.user, event_id=event_id, ip=_client_ip(request)
        )
    except svc.OpsError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return OutboxEventOut(
        id=str(event.id),
        vendor_id=str(event.vendor_id) if event.vendor_id else None,
        event_type=event.event_type,
        status=event.status.value,
        attempts=event.attempts,
        max_attempts=event.max_attempts,
        available_at=event.available_at,
        processed_at=event.processed_at,
        failure_reason=event.failure_reason,
    )


@router.get("/overview", response_model=PlatformOverviewOut)
async def platform_overview(
    ctx: PlatformContext = Depends(require_support),
    db: AsyncSession = Depends(get_db),
) -> PlatformOverviewOut:
    data = await svc.platform_overview(db)
    return PlatformOverviewOut(
        vendors=VendorStatusCountsOut(**data["vendors"]),
        pending_workspace_requests=data["pending_workspace_requests"],
        total_leads=data["total_leads"],
        outbox_failed=data["outbox_failed"],
        recent_signups_7d=data["recent_signups_7d"],
    )
