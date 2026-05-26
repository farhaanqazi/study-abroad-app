"""Platform-user (operator) administration.

Listing platform users and granting/revoking their back-office tier
(``platform_role``). Role changes are SUPERADMIN-only at the route layer; this
service additionally enforces two fail-closed anti-lockout invariants:

  * A superadmin cannot demote THEMSELVES (no accidental self-lockout).
  * The LAST remaining superadmin cannot be demoted (the platform must always
    retain at least one superadmin).

Every change is audited in the same transaction as the role mutation.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PlatformRole
from app.db.models.tenant import User, VendorMembership
from app.services import audit


class PlatformUserError(Exception):
    """Domain error with an HTTP-friendly status hint."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


async def list_users(
    session: AsyncSession,
    *,
    q: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[tuple[User, int]]:
    """List users with their tenant-membership count. Excludes soft-deleted."""
    count_subq = (
        select(
            VendorMembership.user_id.label("uid"),
            func.count().label("cnt"),
        )
        .group_by(VendorMembership.user_id)
        .subquery()
    )
    stmt = (
        select(User, func.coalesce(count_subq.c.cnt, 0))
        .outerjoin(count_subq, count_subq.c.uid == User.id)
        .where(User.deleted_at.is_(None))
    )
    if q:
        stmt = stmt.where(func.lower(User.email).like(f"%{q.strip().lower()}%"))
    stmt = stmt.order_by(User.email.asc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).all()
    return [(u, int(cnt)) for (u, cnt) in rows]


async def _superadmin_count(session: AsyncSession) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.platform_role == PlatformRole.SUPERADMIN,
                User.deleted_at.is_(None),
            )
        )
        or 0
    )


async def set_platform_role(
    session: AsyncSession,
    *,
    actor: User,
    user_id: UUID,
    new_role: PlatformRole,
    ip: Optional[str] = None,
) -> User:
    """Grant or revoke a user's platform role. SUPERADMIN-only (enforced at the
    route). Anti-lockout guards applied here, fail-closed."""
    target = await session.get(User, user_id)
    if target is None or target.deleted_at is not None:
        raise PlatformUserError("User not found.", 404)

    if target.platform_role == new_role:
        return target

    demoting_a_superadmin = (
        target.platform_role == PlatformRole.SUPERADMIN
        and new_role != PlatformRole.SUPERADMIN
    )

    if demoting_a_superadmin:
        # Guard 1: never demote yourself (avoid self-lockout).
        if target.id == actor.id:
            raise PlatformUserError(
                "You cannot demote your own superadmin role.", 409
            )
        # Guard 2: never demote the last remaining superadmin.
        if await _superadmin_count(session) <= 1:
            raise PlatformUserError(
                "Cannot demote the last remaining superadmin.", 409
            )

    old_role = target.platform_role
    target.platform_role = new_role
    await audit.record(
        session,
        actor=actor,
        action="platform_user.role_change",
        target_type="user",
        target_id=target.id,
        details={"from": old_role.value, "to": new_role.value},
        ip=ip,
    )
    await session.commit()
    await session.refresh(target)
    return target
