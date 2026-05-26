"""Vendor membership administration + invitation lifecycle.

Admins manage who belongs to a vendor and with what role. Adding a member who
hasn't authenticated yet is done via an Invitation (claimed on their next
login); if the email already maps to a User we bind the membership directly.

Two invariants are enforced fail-closed in this layer:
  * A vendor must always retain >= 1 owner — the last owner can neither be
    removed nor demoted (prevents orphaning a tenant).
  * At most one OPEN (pending) invitation per (vendor, email).

Every mutation is audited in the same transaction as the change.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import InvitationStatus, UserRole
from app.db.models.invitation import Invitation
from app.db.models.tenant import User, Vendor, VendorMembership
from app.services import audit

# Default invitation validity window.
_DEFAULT_INVITE_TTL = timedelta(days=14)


class MemberAdminError(Exception):
    """Domain error with an HTTP-friendly status hint."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _require_vendor(session: AsyncSession, vendor_id: UUID) -> Vendor:
    vendor = await session.get(Vendor, vendor_id)
    if vendor is None:
        raise MemberAdminError("Vendor not found.", 404)
    return vendor


async def _owner_count(session: AsyncSession, vendor_id: UUID) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(VendorMembership)
            .where(
                VendorMembership.vendor_id == vendor_id,
                VendorMembership.role == UserRole.OWNER,
            )
        )
        or 0
    )


async def list_members(
    session: AsyncSession, *, vendor_id: UUID
) -> list[tuple[VendorMembership, User]]:
    await _require_vendor(session, vendor_id)
    rows = (
        await session.execute(
            select(VendorMembership, User)
            .join(User, User.id == VendorMembership.user_id)
            .where(VendorMembership.vendor_id == vendor_id)
            .order_by(User.email.asc())
        )
    ).all()
    return [(m, u) for (m, u) in rows]


async def invite_member(
    session: AsyncSession,
    *,
    admin: User,
    vendor_id: UUID,
    email: str,
    role: UserRole,
    ttl: Optional[timedelta] = _DEFAULT_INVITE_TTL,
    ip: Optional[str] = None,
) -> dict:
    """Invite an email to a vendor.

    If the email already maps to an existing User, the membership is created
    directly and returned (kind="membership"). Otherwise a pending Invitation
    with a random token is created (kind="invitation"). One open invite per
    (vendor, email) is enforced.
    """
    await _require_vendor(session, vendor_id)
    norm_email = (email or "").strip().lower()
    if not norm_email:
        raise MemberAdminError("Email is required.", 422)

    existing_user = await session.scalar(
        select(User).where(func.lower(User.email) == norm_email)
    )

    if existing_user is not None:
        if existing_user.deleted_at is not None:
            raise MemberAdminError("That user account is deactivated.", 409)
        already = await session.scalar(
            select(VendorMembership).where(
                VendorMembership.user_id == existing_user.id,
                VendorMembership.vendor_id == vendor_id,
            )
        )
        if already is not None:
            raise MemberAdminError("User is already a member of this vendor.", 409)

        membership = VendorMembership(
            user_id=existing_user.id, vendor_id=vendor_id, role=role
        )
        session.add(membership)
        await audit.record(
            session,
            actor=admin,
            action="member.add",
            target_type="user",
            target_id=existing_user.id,
            vendor_id=vendor_id,
            details={"email": norm_email, "role": role.value, "via": "direct"},
            ip=ip,
        )
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise MemberAdminError(
                "User is already a member of this vendor.", 409
            ) from exc
        await session.refresh(membership)
        return {
            "kind": "membership",
            "vendor_id": str(vendor_id),
            "email": norm_email,
            "role": role,
            "user_id": str(existing_user.id),
        }

    # No user yet -> pending invitation. Enforce one open invite per (vendor,email).
    open_invite = await session.scalar(
        select(Invitation).where(
            Invitation.vendor_id == vendor_id,
            func.lower(Invitation.email) == norm_email,
            Invitation.status == InvitationStatus.PENDING,
        )
    )
    if open_invite is not None:
        raise MemberAdminError(
            "An open invitation already exists for this email.", 409
        )

    expires_at = (_now() + ttl) if ttl else None
    invitation = Invitation(
        vendor_id=vendor_id,
        email=norm_email,
        role=role,
        token=secrets.token_urlsafe(32),
        status=InvitationStatus.PENDING,
        invited_by_user_id=admin.id,
        expires_at=expires_at,
    )
    session.add(invitation)
    await audit.record(
        session,
        actor=admin,
        action="member.invite",
        target_type="invitation",
        target_id=None,
        vendor_id=vendor_id,
        details={"email": norm_email, "role": role.value},
        ip=ip,
    )
    await session.flush()
    # Backfill the audit target with the now-assigned invitation id is optional;
    # commit as-is for atomicity.
    await session.commit()
    await session.refresh(invitation)
    return {
        "kind": "invitation",
        "vendor_id": str(vendor_id),
        "email": norm_email,
        "role": role,
        "invitation_id": str(invitation.id),
        "token": invitation.token,
        "expires_at": invitation.expires_at,
    }


async def change_role(
    session: AsyncSession,
    *,
    admin: User,
    vendor_id: UUID,
    user_id: UUID,
    role: UserRole,
    ip: Optional[str] = None,
) -> VendorMembership:
    """Change a member's role. Guard: cannot demote the LAST owner."""
    await _require_vendor(session, vendor_id)
    membership = await session.scalar(
        select(VendorMembership).where(
            VendorMembership.user_id == user_id,
            VendorMembership.vendor_id == vendor_id,
        )
    )
    if membership is None:
        raise MemberAdminError("Membership not found.", 404)

    if membership.role == role:
        return membership

    # Last-owner guard: demoting the sole owner would orphan the tenant.
    if membership.role == UserRole.OWNER and role != UserRole.OWNER:
        if await _owner_count(session, vendor_id) <= 1:
            raise MemberAdminError(
                "Cannot demote the last owner of this vendor.", 409
            )

    old_role = membership.role
    membership.role = role
    await audit.record(
        session,
        actor=admin,
        action="member.role_change",
        target_type="user",
        target_id=user_id,
        vendor_id=vendor_id,
        details={"from": old_role.value, "to": role.value},
        ip=ip,
    )
    await session.commit()
    await session.refresh(membership)
    return membership


async def remove_member(
    session: AsyncSession,
    *,
    admin: User,
    vendor_id: UUID,
    user_id: UUID,
    ip: Optional[str] = None,
) -> None:
    """Remove a membership. Guard: cannot remove the LAST owner."""
    await _require_vendor(session, vendor_id)
    membership = await session.scalar(
        select(VendorMembership).where(
            VendorMembership.user_id == user_id,
            VendorMembership.vendor_id == vendor_id,
        )
    )
    if membership is None:
        raise MemberAdminError("Membership not found.", 404)

    if membership.role == UserRole.OWNER and await _owner_count(session, vendor_id) <= 1:
        raise MemberAdminError("Cannot remove the last owner of this vendor.", 409)

    await session.delete(membership)
    await audit.record(
        session,
        actor=admin,
        action="member.remove",
        target_type="user",
        target_id=user_id,
        vendor_id=vendor_id,
        details={"role": membership.role.value},
        ip=ip,
    )
    await session.commit()


async def claim_invitations_for_user(session: AsyncSession, user: User) -> int:
    """Claim all pending, unexpired invitations for ``user.email``.

    Creates a VendorMembership for each and marks the invitation accepted. Used
    by the auth provisioning path on first/each login. Idempotent: if a
    membership already exists, the invite is still marked accepted (no dup).
    Expired invitations are marked EXPIRED instead of claimed.

    Does NOT commit — the caller commits (so claiming joins the provisioning
    transaction). Returns the number of memberships created.
    """
    norm_email = (user.email or "").strip().lower()
    if not norm_email:
        return 0

    pending = (
        await session.execute(
            select(Invitation).where(
                func.lower(Invitation.email) == norm_email,
                Invitation.status == InvitationStatus.PENDING,
            )
        )
    ).scalars().all()

    created = 0
    now = _now()
    for inv in pending:
        if inv.expires_at is not None and inv.expires_at < now:
            inv.status = InvitationStatus.EXPIRED
            continue

        already = await session.scalar(
            select(VendorMembership).where(
                VendorMembership.user_id == user.id,
                VendorMembership.vendor_id == inv.vendor_id,
            )
        )
        if already is None:
            session.add(
                VendorMembership(
                    user_id=user.id, vendor_id=inv.vendor_id, role=inv.role
                )
            )
            created += 1

        inv.status = InvitationStatus.ACCEPTED
        inv.accepted_by_user_id = user.id
        inv.accepted_at = now

    return created
