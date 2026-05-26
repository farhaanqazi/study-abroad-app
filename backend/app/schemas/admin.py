"""Pydantic v2 schemas for the platform back-office admin APIs.

Create/Out split per the FastAPI patterns skill. Out models use string ids
(UUID -> str) for stable JSON and never expose secrets (e.g. invitation tokens
are returned only on creation, deliberately).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import PlatformRole, UserRole, VendorStatus

# --------------------------------------------------------------------------- vendors


class VendorCreate(BaseModel):
    business_name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=3, max_length=100)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"business_name": "Global Pathways Education", "slug": "global-pathways"}
        }
    )


class VendorUpdate(BaseModel):
    business_name: Optional[str] = Field(None, min_length=1, max_length=255)
    slug: Optional[str] = Field(None, min_length=3, max_length=100)


class VendorOut(BaseModel):
    id: str
    slug: str
    business_name: str
    is_active: bool
    status: VendorStatus
    deleted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class VendorDetailOut(VendorOut):
    member_count: int


# --------------------------------------------------------------------------- members


class MemberOut(BaseModel):
    user_id: str
    email: str
    role: UserRole
    membership_id: str


class InviteCreate(BaseModel):
    # Plain str (not EmailStr) to match the codebase convention and avoid the
    # optional email-validator dependency; format is loosely guarded by pattern.
    email: str = Field(
        ...,
        min_length=3,
        max_length=320,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    role: UserRole = Field(default=UserRole.VIEWER)

    model_config = ConfigDict(
        json_schema_extra={"example": {"email": "agent@example.com", "role": "agent"}}
    )


class MemberRoleUpdate(BaseModel):
    role: UserRole


class InviteResultOut(BaseModel):
    """Result of inviting an email.

    If the email already mapped to an existing user, a membership was created
    directly (``kind="membership"``). Otherwise a pending invitation was created
    (``kind="invitation"``); ``token`` is surfaced ONCE here for delivery.
    """

    kind: str  # "membership" | "invitation"
    vendor_id: str
    email: str
    role: UserRole
    invitation_id: Optional[str] = None
    token: Optional[str] = None
    user_id: Optional[str] = None
    expires_at: Optional[datetime] = None


# --------------------------------------------------------------------------- platform users


class PlatformUserOut(BaseModel):
    id: str
    email: str
    platform_role: PlatformRole
    membership_count: int


class PlatformRoleUpdate(BaseModel):
    platform_role: PlatformRole
