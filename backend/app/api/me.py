from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.dependencies.auth import get_current_user
from app.db.models.tenant import User, Vendor, VendorMembership

# Authenticated identity endpoint. Unlike /console/{vendor_id}/** this is NOT
# tenant-scoped — it tells the just-logged-in caller *which* tenants they belong
# to (and their role in each) so the console can offer a vendor picker. Gated by
# get_current_user only (valid token required; lazily provisions the user).
router = APIRouter(prefix="/me", tags=["me"])


class MembershipOut(BaseModel):
    vendor_id: str
    slug: str
    business_name: str
    role: str


class MeOut(BaseModel):
    id: str
    email: str
    # Platform-operator tier ("none" for ordinary users). The frontend uses this
    # to decide whether to expose the /admin back-office.
    platform_role: str
    memberships: list[MembershipOut]


@router.get("", response_model=MeOut)
async def get_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeOut:
    rows = (
        await db.execute(
            select(VendorMembership, Vendor)
            .join(Vendor, Vendor.id == VendorMembership.vendor_id)
            .where(VendorMembership.user_id == user.id)
            .order_by(Vendor.business_name)
        )
    ).all()
    return MeOut(
        id=str(user.id),
        email=user.email,
        platform_role=user.platform_role.value,
        memberships=[
            MembershipOut(
                vendor_id=str(vendor.id),
                slug=vendor.slug,
                business_name=vendor.business_name,
                role=membership.role.value,
            )
            for (membership, vendor) in rows
        ],
    )
