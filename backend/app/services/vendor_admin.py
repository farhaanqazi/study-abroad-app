"""Back-office vendor (workspace) administration.

Direct admin lifecycle management of vendors: list/search, detail, create,
edit, suspend/activate, and SOFT-delete. Every mutation writes an AuditLog row
in the SAME transaction as the state change (atomic: both commit or neither).

Never hard-deletes a vendor — delete is a soft state transition (status=deleted
+ deleted_at) so the row remains recoverable and audit history stays intact.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import VendorStatus
from app.db.models.tenant import User, Vendor, VendorMembership, VendorSiteConfig
from app.services import audit

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,98}[a-z0-9])$")


class VendorAdminError(Exception):
    """Domain error with an HTTP-friendly status hint."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def normalize_slug(raw: str) -> str:
    slug = (raw or "").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    if not _SLUG_RE.match(slug):
        raise VendorAdminError(
            "Slug must be 3–100 chars: lowercase letters, digits, hyphens.", 422
        )
    return slug


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def list_vendors(
    session: AsyncSession,
    *,
    q: Optional[str] = None,
    status: Optional[VendorStatus] = None,
    include_deleted: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[Vendor]:
    stmt = select(Vendor)
    if not include_deleted:
        stmt = stmt.where(Vendor.status != VendorStatus.DELETED)
    if status is not None:
        stmt = stmt.where(Vendor.status == status)
    if q:
        pattern = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Vendor.slug).like(pattern),
                func.lower(Vendor.business_name).like(pattern),
            )
        )
    stmt = stmt.order_by(Vendor.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)


async def _load_vendor(session: AsyncSession, vendor_id: UUID) -> Vendor:
    vendor = await session.get(Vendor, vendor_id)
    if vendor is None:
        raise VendorAdminError("Vendor not found.", 404)
    return vendor


async def member_count(session: AsyncSession, vendor_id: UUID) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(VendorMembership)
            .where(VendorMembership.vendor_id == vendor_id)
        )
        or 0
    )


async def get_vendor_detail(
    session: AsyncSession, *, vendor_id: UUID
) -> tuple[Vendor, int]:
    vendor = await _load_vendor(session, vendor_id)
    return vendor, await member_count(session, vendor_id)


async def create_vendor(
    session: AsyncSession,
    *,
    admin: User,
    business_name: str,
    slug: str,
    ip: Optional[str] = None,
) -> Vendor:
    """Create a vendor directly (admin path) + a default site config.

    Slug is normalized; collisions are rejected as 409 (pre-check + on the
    unique-constraint race). Audited in the same transaction.
    """
    name = (business_name or "").strip()
    if not name:
        raise VendorAdminError("Business name is required.", 422)
    norm_slug = normalize_slug(slug)

    clash = await session.scalar(select(Vendor).where(Vendor.slug == norm_slug))
    if clash is not None:
        raise VendorAdminError(f"Slug '{norm_slug}' is already taken.", 409)

    vendor = Vendor(
        slug=norm_slug,
        business_name=name,
        is_active=True,
        status=VendorStatus.ACTIVE,
    )
    session.add(vendor)
    await session.flush()  # assign vendor.id

    session.add(VendorSiteConfig(vendor_id=vendor.id, config={}, version=1))

    await audit.record(
        session,
        actor=admin,
        action="vendor.create",
        target_type="vendor",
        target_id=vendor.id,
        vendor_id=vendor.id,
        details={"slug": norm_slug, "business_name": name},
        ip=ip,
    )

    try:
        await session.commit()
    except IntegrityError as exc:  # slug race
        await session.rollback()
        raise VendorAdminError(f"Slug '{norm_slug}' is already taken.", 409) from exc

    await session.refresh(vendor)
    return vendor


async def update_vendor(
    session: AsyncSession,
    *,
    admin: User,
    vendor_id: UUID,
    business_name: Optional[str] = None,
    slug: Optional[str] = None,
    ip: Optional[str] = None,
) -> Vendor:
    vendor = await _load_vendor(session, vendor_id)
    changes: dict[str, object] = {}

    if business_name is not None:
        name = business_name.strip()
        if not name:
            raise VendorAdminError("Business name cannot be empty.", 422)
        if name != vendor.business_name:
            changes["business_name"] = name
            vendor.business_name = name

    if slug is not None:
        norm_slug = normalize_slug(slug)
        if norm_slug != vendor.slug:
            clash = await session.scalar(
                select(Vendor).where(Vendor.slug == norm_slug, Vendor.id != vendor.id)
            )
            if clash is not None:
                raise VendorAdminError(f"Slug '{norm_slug}' is already taken.", 409)
            changes["slug"] = norm_slug
            vendor.slug = norm_slug

    if not changes:
        return vendor

    await audit.record(
        session,
        actor=admin,
        action="vendor.update",
        target_type="vendor",
        target_id=vendor.id,
        vendor_id=vendor.id,
        details=changes,
        ip=ip,
    )

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise VendorAdminError("Slug is already taken.", 409) from exc

    await session.refresh(vendor)
    return vendor


async def _set_status(
    session: AsyncSession,
    *,
    admin: User,
    vendor_id: UUID,
    status: VendorStatus,
    is_active: bool,
    action: str,
    ip: Optional[str],
    deleted_at: Optional[datetime] = None,
) -> Vendor:
    vendor = await _load_vendor(session, vendor_id)
    vendor.status = status
    vendor.is_active = is_active
    if status == VendorStatus.DELETED:
        vendor.deleted_at = deleted_at or _now()
    elif status == VendorStatus.ACTIVE:
        vendor.deleted_at = None

    await audit.record(
        session,
        actor=admin,
        action=action,
        target_type="vendor",
        target_id=vendor.id,
        vendor_id=vendor.id,
        details={"status": status.value, "slug": vendor.slug},
        ip=ip,
    )
    await session.commit()
    await session.refresh(vendor)
    return vendor


async def suspend_vendor(
    session: AsyncSession, *, admin: User, vendor_id: UUID, ip: Optional[str] = None
) -> Vendor:
    return await _set_status(
        session,
        admin=admin,
        vendor_id=vendor_id,
        status=VendorStatus.SUSPENDED,
        is_active=False,
        action="vendor.suspend",
        ip=ip,
    )


async def activate_vendor(
    session: AsyncSession, *, admin: User, vendor_id: UUID, ip: Optional[str] = None
) -> Vendor:
    return await _set_status(
        session,
        admin=admin,
        vendor_id=vendor_id,
        status=VendorStatus.ACTIVE,
        is_active=True,
        action="vendor.activate",
        ip=ip,
    )


async def soft_delete_vendor(
    session: AsyncSession, *, admin: User, vendor_id: UUID, ip: Optional[str] = None
) -> Vendor:
    """SOFT delete only — never a hard DELETE. Sets status=deleted, deleted_at,
    is_active=False. The row (and its audit trail) remain recoverable."""
    return await _set_status(
        session,
        admin=admin,
        vendor_id=vendor_id,
        status=VendorStatus.DELETED,
        is_active=False,
        action="vendor.delete",
        ip=ip,
        deleted_at=_now(),
    )
