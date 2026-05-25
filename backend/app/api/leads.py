from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_app_settings, get_db, get_email_service
from app.core.config import Settings
from app.db.models.leads import (
    Application,
    Callback,
    CostEstimate,
    Inquiry,
    QrLog,
)
from app.db.models.vendor import Vendor
from app.db.models.vendor_cost import VendorCostSetting
from app.middleware.rate_limiter import limiter
from app.schemas.leads import (
    ApplicationCreate,
    CallbackCreate,
    CostEstimateCreate,
    CostEstimateResult,
    CostOption,
    CostOptionsOut,
    InquiryCreate,
    PublicConfigOut,
    QrLogCreate,
    StatsOut,
    SubmitAck,
)
from app.services.email_service import EmailService
from app.services.tenant_service import TenantService

# Public, per-vendor lead capture. Mounted under settings.api_prefix, so full
# paths look like /api/v1/v/{vendor_slug}/inquiries.
router = APIRouter(prefix="/v/{vendor_slug}", tags=["leads"])

_TWO_DP = Decimal("0.01")


async def resolve_vendor(vendor_slug: str, db: AsyncSession = Depends(get_db)) -> Vendor:
    vendor = await TenantService(db).get_vendor_by_slug(vendor_slug)
    if vendor is None:
        raise HTTPException(status_code=404, detail=f"Vendor '{vendor_slug}' not found.")
    return vendor


def _client_ip(request: Request) -> str | None:
    if request.client:
        return request.client.host
    return None


def _queue_lead_email(
    background: BackgroundTasks,
    email: EmailService | None,
    settings: Settings,
    *,
    lead_type: str,
    vendor: Vendor,
    details: dict[str, object],
    student_email: str | None = None,
    student_name: str | None = None,
) -> None:
    if email is None:
        return
    background.add_task(
        email.notify_lead,
        lead_type=lead_type,
        vendor_name=vendor.name,
        business_email=settings.business_email or None,
        details=details,
        student_email=student_email,
        student_name=student_name,
    )


@router.post("/inquiries", response_model=SubmitAck, status_code=201)
@limiter.limit("5 per 5 minutes")
async def create_inquiry(
    request: Request,
    payload: InquiryCreate,
    vendor: Vendor = Depends(resolve_vendor),
    db: AsyncSession = Depends(get_db),
    email: EmailService | None = Depends(get_email_service),
    settings: Settings = Depends(get_app_settings),
    background: BackgroundTasks = None,
) -> SubmitAck:
    row = Inquiry(
        vendor_id=vendor.id,
        name=payload.name,
        email=payload.email,
        message=payload.message,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    _queue_lead_email(
        background, email, settings,
        lead_type="inquiry", vendor=vendor,
        details={"Name": payload.name, "Email": payload.email, "Message": payload.message},
        student_email=payload.email, student_name=payload.name,
    )
    return SubmitAck(id=row.id)


@router.post("/callback", response_model=SubmitAck, status_code=201)
@limiter.limit("3 per 10 minutes")
async def create_callback(
    request: Request,
    payload: CallbackCreate,
    vendor: Vendor = Depends(resolve_vendor),
    db: AsyncSession = Depends(get_db),
    email: EmailService | None = Depends(get_email_service),
    settings: Settings = Depends(get_app_settings),
    background: BackgroundTasks = None,
) -> SubmitAck:
    row = Callback(
        vendor_id=vendor.id,
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        preferred_time=payload.preferred_time,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    _queue_lead_email(
        background, email, settings,
        lead_type="callback request", vendor=vendor,
        details={
            "Name": payload.name, "Phone": payload.phone,
            "Email": payload.email, "Preferred time": payload.preferred_time,
        },
        student_email=payload.email, student_name=payload.name,
    )
    return SubmitAck(id=row.id)


@router.post("/applications", response_model=SubmitAck, status_code=201)
@limiter.limit("3 per 10 minutes")
async def create_application(
    request: Request,
    payload: ApplicationCreate,
    vendor: Vendor = Depends(resolve_vendor),
    db: AsyncSession = Depends(get_db),
    email: EmailService | None = Depends(get_email_service),
    settings: Settings = Depends(get_app_settings),
    background: BackgroundTasks = None,
) -> SubmitAck:
    row = Application(
        vendor_id=vendor.id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        education=payload.education,
        course=payload.course,
        country=payload.country,
        intake=payload.intake,
        message=payload.message,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    _queue_lead_email(
        background, email, settings,
        lead_type="application", vendor=vendor,
        details={
            "Name": payload.name, "Email": payload.email, "Phone": payload.phone,
            "Education": payload.education, "Course": payload.course,
            "Country": payload.country, "Intake": payload.intake,
            "Message": payload.message,
        },
        student_email=payload.email, student_name=payload.name,
    )
    return SubmitAck(id=row.id)


@router.post("/qr/log", response_model=SubmitAck, status_code=201)
async def log_qr(
    request: Request,
    payload: QrLogCreate,
    vendor: Vendor = Depends(resolve_vendor),
    db: AsyncSession = Depends(get_db),
) -> SubmitAck:
    # Fire-and-forget: no rate limit, no email.
    row = QrLog(vendor_id=vendor.id, url=payload.url, ip=_client_ip(request))
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return SubmitAck(id=row.id)


@router.get("/config", response_model=PublicConfigOut)
async def get_public_config(vendor: Vendor = Depends(resolve_vendor)) -> PublicConfigOut:
    return PublicConfigOut(vendor_name=vendor.name, vendor_slug=vendor.slug)


@router.get("/stats", response_model=StatsOut)
async def get_stats(
    vendor: Vendor = Depends(resolve_vendor),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> StatsOut:
    # Baselines + this vendor's real application count (mirrors Horizon /stats).
    app_count = await db.scalar(
        select(func.count()).select_from(Application).where(Application.vendor_id == vendor.id)
    )
    return StatsOut(
        students=settings.base_students + int(app_count or 0),
        countries=settings.base_countries,
        universities=settings.base_universities,
        experience=settings.base_experience,
    )


@router.get("/cost-options", response_model=CostOptionsOut)
async def get_cost_options(
    vendor: Vendor = Depends(resolve_vendor),
    db: AsyncSession = Depends(get_db),
) -> CostOptionsOut:
    rows = (
        await db.execute(
            select(VendorCostSetting)
            .where(
                VendorCostSetting.vendor_id == vendor.id,
                VendorCostSetting.is_active.is_(True),
            )
            .order_by(VendorCostSetting.country, VendorCostSetting.study_level)
        )
    ).scalars().all()
    return CostOptionsOut(
        options=[
            CostOption(country=r.country, study_level=r.study_level, currency=r.currency)
            for r in rows
        ]
    )


@router.post("/cost-estimate", response_model=CostEstimateResult, status_code=201)
@limiter.limit("5 per 10 minutes")
async def create_cost_estimate(
    request: Request,
    payload: CostEstimateCreate,
    vendor: Vendor = Depends(resolve_vendor),
    db: AsyncSession = Depends(get_db),
    email: EmailService | None = Depends(get_email_service),
    settings: Settings = Depends(get_app_settings),
    background: BackgroundTasks = None,
) -> CostEstimateResult:
    setting = await _resolve_cost_setting(db, vendor.id, payload.country, payload.study_level)
    if setting is None:
        raise HTTPException(
            status_code=422,
            detail=f"No cost data configured for country '{payload.country}'.",
        )

    months = Decimal(payload.duration_months)
    years = months / Decimal(12)
    tuition = (setting.tuition_per_year * years).quantize(_TWO_DP, rounding=ROUND_HALF_UP)
    stay = (setting.rent_per_month * months).quantize(_TWO_DP, rounding=ROUND_HALF_UP)
    food = (setting.food_per_month * months).quantize(_TWO_DP, rounding=ROUND_HALF_UP)
    total = (tuition + stay + food).quantize(_TWO_DP, rounding=ROUND_HALF_UP)

    row = CostEstimate(
        vendor_id=vendor.id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        country=payload.country,
        study_level=payload.study_level,
        course=payload.course,
        intake=payload.intake,
        duration_months=payload.duration_months,
        currency=setting.currency,
        est_tuition=tuition,
        est_stay=stay,
        est_food=food,
        est_total=total,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    _queue_lead_email(
        background, email, settings,
        lead_type="cost estimate", vendor=vendor,
        details={
            "Name": payload.name, "Email": payload.email, "Phone": payload.phone,
            "Country": payload.country, "Study level": payload.study_level,
            "Duration (months)": payload.duration_months,
            "Estimated total": f"{setting.currency} {total}",
        },
        student_email=payload.email, student_name=payload.name,
    )

    return CostEstimateResult(
        id=row.id,
        currency=setting.currency,
        country=payload.country,
        study_level=payload.study_level,
        duration_months=payload.duration_months,
        tuition=tuition,
        stay=stay,
        food=food,
        total=total,
    )


async def _resolve_cost_setting(
    db: AsyncSession, vendor_id, country: str, study_level: str | None
) -> VendorCostSetting | None:
    """Prefer an exact (country, study_level) row, else the country-wide 'any' row."""
    levels = [study_level, "any"] if study_level and study_level != "any" else ["any"]
    rows = (
        await db.execute(
            select(VendorCostSetting).where(
                VendorCostSetting.vendor_id == vendor_id,
                VendorCostSetting.is_active.is_(True),
                VendorCostSetting.country == country,
                VendorCostSetting.study_level.in_(levels),
            )
        )
    ).scalars().all()
    by_level = {r.study_level: r for r in rows}
    for level in levels:
        if level in by_level:
            return by_level[level]
    return None
