"""Admin: direct vendor (workspace) lifecycle management.

Read endpoints require SUPPORT+ (operators can triage). Mutations require
ADMIN+. Delete is SOFT only. Every mutation is audited inside its transaction
(handled in the service layer).
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.dependencies.auth import PlatformContext, PlatformRequire
from app.core.enums import PlatformRole, VendorStatus
from app.db.models.tenant import Vendor
from app.schemas.admin import VendorCreate, VendorDetailOut, VendorOut, VendorUpdate
from app.services import vendor_admin as svc

router = APIRouter(prefix="/vendors", tags=["admin: vendors"])

require_support = PlatformRequire(PlatformRole.SUPPORT)
require_admin = PlatformRequire(PlatformRole.ADMIN)


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _vendor_out(v: Vendor) -> VendorOut:
    return VendorOut(
        id=str(v.id),
        slug=v.slug,
        business_name=v.business_name,
        is_active=v.is_active,
        status=v.status,
        deleted_at=v.deleted_at,
        created_at=v.created_at,
        updated_at=v.updated_at,
    )


@router.get("", response_model=list[VendorOut])
async def list_vendors(
    ctx: PlatformContext = Depends(require_support),
    db: AsyncSession = Depends(get_db),
    q: Optional[str] = Query(None, description="Search slug / business name."),
    status: Optional[VendorStatus] = Query(None, description="Filter by status."),
    include_deleted: bool = Query(False, description="Include soft-deleted vendors."),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[VendorOut]:
    vendors = await svc.list_vendors(
        db,
        q=q,
        status=status,
        include_deleted=include_deleted,
        limit=limit,
        offset=offset,
    )
    return [_vendor_out(v) for v in vendors]


@router.get("/{vendor_id}", response_model=VendorDetailOut)
async def get_vendor(
    vendor_id: UUID,
    ctx: PlatformContext = Depends(require_support),
    db: AsyncSession = Depends(get_db),
) -> VendorDetailOut:
    try:
        vendor, count = await svc.get_vendor_detail(db, vendor_id=vendor_id)
    except svc.VendorAdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    base = _vendor_out(vendor)
    return VendorDetailOut(**base.model_dump(), member_count=count)


@router.post("", response_model=VendorOut, status_code=201)
async def create_vendor(
    payload: VendorCreate,
    request: Request,
    ctx: PlatformContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> VendorOut:
    try:
        vendor = await svc.create_vendor(
            db,
            admin=ctx.user,
            business_name=payload.business_name,
            slug=payload.slug,
            ip=_client_ip(request),
        )
    except svc.VendorAdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return _vendor_out(vendor)


@router.patch("/{vendor_id}", response_model=VendorOut)
async def update_vendor(
    vendor_id: UUID,
    payload: VendorUpdate,
    request: Request,
    ctx: PlatformContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> VendorOut:
    try:
        vendor = await svc.update_vendor(
            db,
            admin=ctx.user,
            vendor_id=vendor_id,
            business_name=payload.business_name,
            slug=payload.slug,
            ip=_client_ip(request),
        )
    except svc.VendorAdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return _vendor_out(vendor)


@router.post("/{vendor_id}/suspend", response_model=VendorOut)
async def suspend_vendor(
    vendor_id: UUID,
    request: Request,
    ctx: PlatformContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> VendorOut:
    try:
        vendor = await svc.suspend_vendor(
            db, admin=ctx.user, vendor_id=vendor_id, ip=_client_ip(request)
        )
    except svc.VendorAdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return _vendor_out(vendor)


@router.post("/{vendor_id}/activate", response_model=VendorOut)
async def activate_vendor(
    vendor_id: UUID,
    request: Request,
    ctx: PlatformContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> VendorOut:
    try:
        vendor = await svc.activate_vendor(
            db, admin=ctx.user, vendor_id=vendor_id, ip=_client_ip(request)
        )
    except svc.VendorAdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return _vendor_out(vendor)


@router.delete("/{vendor_id}", response_model=VendorOut)
async def delete_vendor(
    vendor_id: UUID,
    request: Request,
    ctx: PlatformContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> VendorOut:
    """SOFT delete only — sets status=deleted + deleted_at, never hard-deletes."""
    try:
        vendor = await svc.soft_delete_vendor(
            db, admin=ctx.user, vendor_id=vendor_id, ip=_client_ip(request)
        )
    except svc.VendorAdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return _vendor_out(vendor)
