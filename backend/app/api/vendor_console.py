from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models.leads import Application, Callback, CostEstimate, Inquiry
from app.db.models.vendor import Vendor
from app.db.models.vendor_cost import VendorCostSetting
from app.schemas.leads import (
    ApplicationOut,
    CallbackOut,
    CostEstimateOut,
    InquiryOut,
    VendorCostSettingIn,
    VendorCostSettingOut,
)

# Vendor-facing management console. Scoped by vendor_id in the path (auth is
# deferred — see project decisions; real login will derive vendor_id from the
# session and these handlers stay the same shape).
router = APIRouter(prefix="/vendors/{vendor_id}", tags=["vendor-console"])


async def resolve_vendor_by_id(vendor_id: UUID, db: AsyncSession = Depends(get_db)) -> Vendor:
    vendor = await db.get(Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found.")
    return vendor


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
    vendor: Vendor = Depends(resolve_vendor_by_id),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return await _list(db, Inquiry, vendor.id, limit, offset)


@router.get("/callbacks", response_model=list[CallbackOut])
async def list_callbacks(
    vendor: Vendor = Depends(resolve_vendor_by_id),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return await _list(db, Callback, vendor.id, limit, offset)


@router.get("/applications", response_model=list[ApplicationOut])
async def list_applications(
    vendor: Vendor = Depends(resolve_vendor_by_id),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return await _list(db, Application, vendor.id, limit, offset)


@router.get("/cost-estimates", response_model=list[CostEstimateOut])
async def list_cost_estimates(
    vendor: Vendor = Depends(resolve_vendor_by_id),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return await _list(db, CostEstimate, vendor.id, limit, offset)


# --- Cost settings (CRUD) ---------------------------------------------------

@router.get("/cost-settings", response_model=list[VendorCostSettingOut])
async def list_cost_settings(
    vendor: Vendor = Depends(resolve_vendor_by_id),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(VendorCostSetting)
            .where(VendorCostSetting.vendor_id == vendor.id)
            .order_by(VendorCostSetting.country, VendorCostSetting.study_level)
        )
    ).scalars().all()
    return rows


@router.post("/cost-settings", response_model=VendorCostSettingOut, status_code=201)
async def create_cost_setting(
    payload: VendorCostSettingIn,
    vendor: Vendor = Depends(resolve_vendor_by_id),
    db: AsyncSession = Depends(get_db),
):
    row = VendorCostSetting(vendor_id=vendor.id, **payload.model_dump())
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
    vendor: Vendor = Depends(resolve_vendor_by_id),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(VendorCostSetting, setting_id)
    if row is None or row.vendor_id != vendor.id:
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
    vendor: Vendor = Depends(resolve_vendor_by_id),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(VendorCostSetting, setting_id)
    if row is None or row.vendor_id != vendor.id:
        raise HTTPException(status_code=404, detail="Cost setting not found.")
    await db.delete(row)
    await db.commit()
