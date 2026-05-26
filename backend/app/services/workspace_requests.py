"""Workspace (vendor) provisioning via an admin-approved request queue.

A user with no workspace submits a request; an admin approves it, which
atomically provisions the Vendor + owner membership + default site config and
marks the request approved. All state changes here are single-transaction.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserRole, VendorStatus, WorkspaceRequestStatus
from app.db.models.platform import WorkspaceRequest
from app.db.models.tenant import User, Vendor, VendorMembership, VendorSiteConfig
from app.services import audit

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,98}[a-z0-9])$")


class WorkspaceRequestError(Exception):
    """Domain error with an HTTP-friendly status hint."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def normalize_slug(raw: str) -> str:
    slug = (raw or "").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    if not _SLUG_RE.match(slug):
        raise WorkspaceRequestError(
            "Slug must be 3–100 chars: lowercase letters, digits, hyphens.", 422
        )
    return slug


async def submit_request(
    session: AsyncSession,
    *,
    user: User,
    business_name: str,
    desired_slug: str,
    justification: Optional[str],
) -> WorkspaceRequest:
    """Create a pending request. One open request per user at a time."""
    if not business_name.strip():
        raise WorkspaceRequestError("Business name is required.", 422)
    slug = normalize_slug(desired_slug)

    existing_pending = await session.scalar(
        select(WorkspaceRequest).where(
            WorkspaceRequest.requested_by_user_id == user.id,
            WorkspaceRequest.status == WorkspaceRequestStatus.PENDING,
        )
    )
    if existing_pending is not None:
        raise WorkspaceRequestError(
            "You already have a pending workspace request.", 409
        )

    req = WorkspaceRequest(
        requested_by_user_id=user.id,
        business_name=business_name.strip(),
        desired_slug=slug,
        justification=(justification or None),
    )
    session.add(req)
    await session.commit()
    await session.refresh(req)
    return req


async def list_own_requests(session: AsyncSession, *, user: User) -> list[WorkspaceRequest]:
    rows = (
        await session.execute(
            select(WorkspaceRequest)
            .where(WorkspaceRequest.requested_by_user_id == user.id)
            .order_by(WorkspaceRequest.created_at.desc())
        )
    ).scalars().all()
    return list(rows)


async def _load_pending(session: AsyncSession, request_id: UUID) -> WorkspaceRequest:
    req = await session.get(WorkspaceRequest, request_id)
    if req is None:
        raise WorkspaceRequestError("Workspace request not found.", 404)
    if req.status != WorkspaceRequestStatus.PENDING:
        raise WorkspaceRequestError(
            f"Request is already {req.status.value}; only pending requests can be acted on.", 409
        )
    return req


async def approve_request(
    session: AsyncSession,
    *,
    admin: User,
    request_id: UUID,
    slug_override: Optional[str] = None,
    ip: Optional[str] = None,
) -> tuple[WorkspaceRequest, Vendor]:
    """Approve a pending request → provision Vendor + owner membership + site
    config, mark approved, write audit. All in one transaction."""
    req = await _load_pending(session, request_id)
    slug = normalize_slug(slug_override) if slug_override else req.desired_slug

    clash = await session.scalar(select(Vendor).where(Vendor.slug == slug))
    if clash is not None:
        raise WorkspaceRequestError(
            f"Slug '{slug}' is already taken; approve with a different slug.", 409
        )

    vendor = Vendor(
        slug=slug,
        business_name=req.business_name,
        is_active=True,
        status=VendorStatus.ACTIVE,
    )
    session.add(vendor)
    await session.flush()  # assign vendor.id

    session.add(
        VendorMembership(
            user_id=req.requested_by_user_id,
            vendor_id=vendor.id,
            role=UserRole.OWNER,
        )
    )
    session.add(VendorSiteConfig(vendor_id=vendor.id, config={}, version=1))

    req.status = WorkspaceRequestStatus.APPROVED
    req.reviewed_by_user_id = admin.id
    req.reviewed_at = datetime.now(timezone.utc)
    req.created_vendor_id = vendor.id

    await audit.record(
        session,
        actor=admin,
        action="workspace_request.approve",
        target_type="workspace_request",
        target_id=req.id,
        vendor_id=vendor.id,
        details={"slug": slug, "business_name": req.business_name,
                 "requested_by": str(req.requested_by_user_id)},
        ip=ip,
    )

    try:
        await session.commit()
    except IntegrityError as exc:  # slug race
        await session.rollback()
        raise WorkspaceRequestError(f"Slug '{slug}' is already taken.", 409) from exc

    await session.refresh(req)
    await session.refresh(vendor)
    return req, vendor


async def reject_request(
    session: AsyncSession,
    *,
    admin: User,
    request_id: UUID,
    reason: Optional[str] = None,
    ip: Optional[str] = None,
) -> WorkspaceRequest:
    req = await _load_pending(session, request_id)
    req.status = WorkspaceRequestStatus.REJECTED
    req.reviewed_by_user_id = admin.id
    req.reviewed_at = datetime.now(timezone.utc)
    req.rejection_reason = (reason or None)

    await audit.record(
        session,
        actor=admin,
        action="workspace_request.reject",
        target_type="workspace_request",
        target_id=req.id,
        details={"reason": reason or ""},
        ip=ip,
    )
    await session.commit()
    await session.refresh(req)
    return req
