from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Optional
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

# Lightweight email check (email-validator is not a dependency, so we avoid
# pydantic's EmailStr). Mirrors Horizon's hand-rolled isEmail.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(value: str) -> str:
    value = value.strip()
    if not _EMAIL_RE.match(value):
        raise ValueError("invalid email address")
    return value


EmailField = Annotated[str, AfterValidator(_validate_email)]


# --- Public capture: request bodies -----------------------------------------

class InquiryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailField
    message: str = Field(min_length=1, max_length=5000)


class CallbackCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=3, max_length=40)
    email: Optional[EmailField] = None
    preferred_time: Optional[str] = Field(default=None, max_length=120)


class ApplicationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailField
    phone: str = Field(min_length=3, max_length=40)
    education: Optional[str] = Field(default=None, max_length=255)
    course: Optional[str] = Field(default=None, max_length=255)
    country: Optional[str] = Field(default=None, max_length=120)
    intake: Optional[str] = Field(default=None, max_length=120)
    message: Optional[str] = Field(default=None, max_length=5000)


class QrLogCreate(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class CostEstimateCreate(BaseModel):
    # gated contact capture
    name: str = Field(min_length=1, max_length=255)
    email: EmailField
    phone: str = Field(min_length=3, max_length=40)
    # inputs
    country: str = Field(min_length=1, max_length=120)
    study_level: Optional[str] = Field(default=None, max_length=60)
    course: Optional[str] = Field(default=None, max_length=255)
    intake: Optional[str] = Field(default=None, max_length=120)
    duration_months: int = Field(ge=1, le=120)


# --- Public capture: responses ----------------------------------------------

class SubmitAck(BaseModel):
    ok: bool = True
    id: UUID


class CostEstimateResult(BaseModel):
    ok: bool = True
    id: UUID
    currency: str
    country: str
    study_level: Optional[str] = None
    duration_months: int
    tuition: Decimal
    stay: Decimal
    food: Decimal
    total: Decimal


class CostOption(BaseModel):
    country: str
    study_level: str
    currency: str


class CostOptionsOut(BaseModel):
    options: list[CostOption]


class PublicConfigOut(BaseModel):
    vendor_name: str
    vendor_slug: str
    business_email: Optional[str] = None


class StatsOut(BaseModel):
    ok: bool = True
    students: int
    countries: int
    universities: int
    experience: int


# --- Vendor cost settings (management CRUD) ---------------------------------

class VendorCostSettingIn(BaseModel):
    country: str = Field(min_length=1, max_length=120)
    study_level: str = Field(default="any", max_length=60)
    currency: str = Field(default="USD", max_length=10)
    tuition_per_year: Decimal = Field(ge=0)
    rent_per_month: Decimal = Field(ge=0)
    food_per_month: Decimal = Field(ge=0)
    is_active: bool = True


class VendorCostSettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vendor_id: UUID
    country: str
    study_level: str
    currency: str
    tuition_per_year: Decimal
    rent_per_month: Decimal
    food_per_month: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime


# --- Leads list (management read) -------------------------------------------

class InquiryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vendor_id: UUID
    name: str
    email: str
    message: str
    created_at: datetime


class CallbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vendor_id: UUID
    name: str
    phone: str
    email: Optional[str] = None
    preferred_time: Optional[str] = None
    created_at: datetime


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vendor_id: UUID
    name: str
    email: str
    phone: str
    education: Optional[str] = None
    course: Optional[str] = None
    country: Optional[str] = None
    intake: Optional[str] = None
    message: Optional[str] = None
    created_at: datetime


class CostEstimateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vendor_id: UUID
    name: str
    email: str
    phone: str
    country: str
    study_level: Optional[str] = None
    course: Optional[str] = None
    intake: Optional[str] = None
    duration_months: int
    currency: Optional[str] = None
    est_tuition: Optional[Decimal] = None
    est_stay: Optional[Decimal] = None
    est_food: Optional[Decimal] = None
    est_total: Optional[Decimal] = None
    created_at: datetime
