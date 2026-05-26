from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.dependencies.auth import TenantContext, TenantRequire
from app.core.enums import UserRole
from app.db.models.leads import Application, Callback, CostEstimate, Inquiry
from app.db.models.tenant import VendorSiteConfig
from app.db.models.vendor_cost import VendorCostSetting
from app.schemas.leads import (
    ApplicationOut,
    CallbackOut,
    CostEstimateOut,
    InquiryOut,
    VendorCostSettingIn,
    VendorCostSettingOut,
)
from app.schemas.site import SiteConfig, SiteConfigState

# Authenticated, tenant-scoped management console. Every route is gated by a
# TenantRequire dependency: the caller must present a valid Clerk token (401 if
# not) AND hold a membership on the {vendor_id} in the path with sufficient role
# (403 otherwise). vendor_id is taken from the authenticated context, never
# trusted from the path alone for data access.
router = APIRouter(prefix="/console/{vendor_id}", tags=["vendor-console"])

# Role gates (factory pattern): reads need any member; writes need agent+.
require_viewer = TenantRequire(UserRole.VIEWER)
require_agent = TenantRequire(UserRole.AGENT)


async def _list(db: AsyncSession, model, vendor_id: UUID, limit: int, offset: int):
    rows = (
        await db.execute(
            select(model)
            .where(model.vendor_id == vendor_id)
            .order_by(model.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return rows


# --- Leads (read-only) ------------------------------------------------------

@router.get("/inquiries", response_model=list[InquiryOut])
async def list_inquiries(
    ctx: TenantContext = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return await _list(db, Inquiry, ctx.vendor_id, limit, offset)


@router.get("/callbacks", response_model=list[CallbackOut])
async def list_callbacks(
    ctx: TenantContext = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return await _list(db, Callback, ctx.vendor_id, limit, offset)


@router.get("/applications", response_model=list[ApplicationOut])
async def list_applications(
    ctx: TenantContext = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return await _list(db, Application, ctx.vendor_id, limit, offset)


@router.get("/cost-estimates", response_model=list[CostEstimateOut])
async def list_cost_estimates(
    ctx: TenantContext = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return await _list(db, CostEstimate, ctx.vendor_id, limit, offset)


# --- Cost settings (CRUD) ---------------------------------------------------

@router.get("/cost-settings", response_model=list[VendorCostSettingOut])
async def list_cost_settings(
    ctx: TenantContext = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(VendorCostSetting)
            .where(VendorCostSetting.vendor_id == ctx.vendor_id)
            .order_by(VendorCostSetting.country, VendorCostSetting.study_level)
        )
    ).scalars().all()
    return rows


@router.post("/cost-settings", response_model=VendorCostSettingOut, status_code=201)
async def create_cost_setting(
    payload: VendorCostSettingIn,
    ctx: TenantContext = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    row = VendorCostSetting(vendor_id=ctx.vendor_id, **payload.model_dump())
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A cost setting for this country and study level already exists.",
        )
    await db.refresh(row)
    return row


@router.put("/cost-settings/{setting_id}", response_model=VendorCostSettingOut)
async def update_cost_setting(
    setting_id: UUID,
    payload: VendorCostSettingIn,
    ctx: TenantContext = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(VendorCostSetting, setting_id)
    if row is None or row.vendor_id != ctx.vendor_id:
        raise HTTPException(status_code=404, detail="Cost setting not found.")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A cost setting for this country and study level already exists.",
        )
    await db.refresh(row)
    return row


@router.delete("/cost-settings/{setting_id}", status_code=204)
async def delete_cost_setting(
    setting_id: UUID,
    ctx: TenantContext = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(VendorCostSetting, setting_id)
    if row is None or row.vendor_id != ctx.vendor_id:
        raise HTTPException(status_code=404, detail="Cost setting not found.")
    await db.delete(row)
    await db.commit()


# --- Site configuration (draft → publish) -----------------------------------

def _state(row: VendorSiteConfig | None) -> SiteConfigState:
    """Build the GET response from a (possibly missing) config row."""
    if row is None:
        return SiteConfigState(
            published=SiteConfig(), draft=None, version=0, has_unpublished_changes=False
        )
    return SiteConfigState(
        published=SiteConfig.model_validate(row.config or {}),
        draft=SiteConfig.model_validate(row.draft_config) if row.draft_config else None,
        version=row.version,
        has_unpublished_changes=row.draft_config is not None,
    )


@router.get("/site", response_model=SiteConfigState)
async def get_site_config(
    ctx: TenantContext = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    return _state(await db.get(VendorSiteConfig, ctx.vendor_id))


@router.put("/site/draft", response_model=SiteConfigState)
async def save_site_draft(
    payload: SiteConfig,
    ctx: TenantContext = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(VendorSiteConfig, ctx.vendor_id)
    if row is None:
        row = VendorSiteConfig(vendor_id=ctx.vendor_id, config={}, draft_config=payload.model_dump())
        db.add(row)
    else:
        row.draft_config = payload.model_dump()
        row.updated_by = ctx.user.id
    await db.commit()
    await db.refresh(row)
    return _state(row)


@router.post("/site/publish", response_model=SiteConfigState)
async def publish_site(
    ctx: TenantContext = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(VendorSiteConfig, ctx.vendor_id)
    if row is None or row.draft_config is None:
        raise HTTPException(status_code=409, detail="Nothing to publish — save a draft first.")
    row.config = row.draft_config
    row.draft_config = None
    row.version = (row.version or 0) + 1
    row.updated_by = ctx.user.id
    await db.commit()
    await db.refresh(row)
    return _state(row)
