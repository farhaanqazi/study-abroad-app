"""FastAPI auth/authz request dependencies.

Layering:
  * The provider layer (``app.core.auth``) knows how to verify a bearer token and
    nothing about FastAPI or the database. It fails CLOSED — a returned
    ``AuthClaims`` is proof the token is fully trusted.
  * This module bridges that contract into HTTP: it extracts the bearer token,
    verifies it, lazily provisions the local ``User`` row, and enforces
    per-tenant authorization via the :class:`TenantRequire` factory.

Security posture:
  * Verification failures map to HTTP 401, authorization failures to HTTP 403.
    The client never sees *why* (no key ids, claim names, db errors) — the
    internal reason is logged server-side via structlog only.
  * No fail-open path: a misconfigured provider raises ``AuthError`` upstream,
    which becomes a 401 here, never an accidental "allow".
  * Tokens and secrets are NEVER logged. We log the (already public) clerk
    subject + vendor id for audit, nothing more.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Optional
from uuid import UUID

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthClaims, AuthError, IdentityProvider
from app.core.auth.clerk_provider import ClerkProvider
from app.core.config import Settings, get_settings
from app.core.enums import PlatformRole, UserRole
from app.db.models.tenant import User, VendorMembership
from app.db.session import get_session

logger = structlog.get_logger(__name__)

# HTTPBearer with auto_error=False: a missing/blank/non-bearer Authorization
# header yields None credentials, which get_current_user maps to a uniform 401
# (FastAPI's auto_error=True would instead raise 403 on a missing header).
_bearer_scheme = HTTPBearer(auto_error=False, scheme_name="ClerkBearer")

# Role hierarchy: a caller with a higher-privileged role implicitly satisfies a
# requirement for any lower-privileged role. owner > agent > viewer.
_ROLE_RANK: dict[UserRole, int] = {
    UserRole.OWNER: 3,
    UserRole.AGENT: 2,
    UserRole.VIEWER: 1,
}

# Platform-operator hierarchy. NONE (rank 0) never satisfies a platform
# requirement — it is the "no back-office access" floor.
_PLATFORM_RANK: dict[PlatformRole, int] = {
    PlatformRole.SUPERADMIN: 3,
    PlatformRole.ADMIN: 2,
    PlatformRole.SUPPORT: 1,
    PlatformRole.NONE: 0,
}


@lru_cache(maxsize=1)
def get_identity_provider() -> IdentityProvider:
    """Process-wide cached identity provider.

    Cached so the JWKS key cache (held on the provider instance) survives across
    requests. Swap-friendly for tests via dependency_overrides on this callable.
    """
    return ClerkProvider()


def _current_request(request: Request) -> Request:
    """Trivial dependency that surfaces the active Request.

    Used by :class:`TenantRequire` to read the ``vendor_id`` path param. Defined
    as a standalone function (not a typed param on the class ``__call__``) so
    FastAPI reliably resolves the ``Request`` annotation despite this module's
    ``from __future__ import annotations``.
    """
    return request


_RequestDep = Depends(_current_request)


@dataclass(frozen=True)
class TenantContext:
    """Authenticated + authorized request context for a tenant-scoped route.

    Produced by :class:`TenantRequire`. Carries the resolved local user, the
    target vendor (tenant) id from the path, and the caller's role in that
    tenant. The mere existence of this object is proof the caller is both
    authenticated and authorized for the requested role level.
    """

    user: User
    vendor_id: UUID
    role: UserRole


def _unauthorized() -> HTTPException:
    # Uniform 401 — no detail about *why* the token was rejected.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient permissions for this tenant",
    )


async def _provision_user(session: AsyncSession, claims: AuthClaims) -> User:
    """Return the local ``User`` for these claims, inserting on first sight.

    Lazy provisioning: a verified identity we have never seen is materialized as
    a ``User`` row keyed by ``clerk_id`` (with ``email`` mirrored from the IdP).
    Two concurrent first-requests for the same identity race on the unique
    ``clerk_id``/``email`` constraints; we catch the IntegrityError, roll back,
    and re-read the row the winner committed.
    """
    clerk_id = claims.clerk_id
    # Prefer the real email claim. Clerk's DEFAULT session token doesn't include
    # one, so fall back to a stable, unique placeholder derived from the clerk_id
    # — enough to provision (email is NOT NULL + unique) without forcing every
    # deployment to customize Clerk's session-token claims. Add `email` to the
    # Clerk session token to get real addresses in the console.
    email = claims.email or f"{clerk_id}@users.noreply.clerk"

    existing = await session.scalar(select(User).where(User.clerk_id == clerk_id))
    if existing is not None:
        return existing

    user = User(clerk_id=clerk_id, email=email)
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        # Lost the provisioning race (or email already bound to another clerk_id).
        # Roll back this unit of work and re-read the committed row by clerk_id.
        await session.rollback()
        existing = await session.scalar(select(User).where(User.clerk_id == clerk_id))
        if existing is None:
            # Conflict was on email (bound to a different clerk_id) — not a race
            # we can recover. Surface as auth failure, never expose the conflict.
            logger.warning("user_provision_conflict", clerk_id=clerk_id)
            raise AuthError(reason="identity conflict during provisioning")
        return existing

    await session.commit()
    logger.info("user_provisioned", clerk_id=clerk_id, user_id=str(user.id))
    return user


async def _sync_bootstrap_superadmin(session: AsyncSession, user: User, settings: Settings) -> None:
    """Promote a user to superadmin iff their clerk_id/email is in the env
    allowlist. FAIL-CLOSED: empty allowlist promotes nobody. Promotion-only —
    demotion is a deliberate in-console action, never an env side effect (so a
    config slip can't silently strip the last admin mid-session).
    """
    allow = settings.platform_superadmin_set
    if not allow:
        return
    if user.platform_role == PlatformRole.SUPERADMIN:
        return
    identity = {user.clerk_id.lower(), (user.email or "").lower()}
    if identity & allow:
        user.platform_role = PlatformRole.SUPERADMIN
        await session.commit()
        logger.info("platform_superadmin_bootstrapped", user_id=str(user.id))


async def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
    provider: Annotated[IdentityProvider, Depends(get_identity_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """Verify the bearer token and return the (lazily provisioned) local user.

    Raises 401 on any verification or provisioning failure. Never leaks the
    underlying reason to the client.
    """
    token = credentials.credentials if credentials else None
    if not token:
        raise _unauthorized()

    try:
        claims = await provider.verify(token)
    except AuthError as exc:
        logger.info("auth_token_rejected", reason=exc.reason)
        raise _unauthorized() from exc

    try:
        user = await _provision_user(session, claims)
    except AuthError as exc:
        logger.info("auth_provision_rejected", reason=exc.reason)
        raise _unauthorized() from exc

    if user.deleted_at is not None:
        # Soft-deleted identities are not authenticatable.
        logger.info("auth_user_deleted", clerk_id=claims.clerk_id)
        raise _unauthorized()

    await _sync_bootstrap_superadmin(session, user, settings)

    # Claim any pending invitations addressed to this user's email (created by an
    # admin/owner before the invitee first logged in). Idempotent + cheap.
    try:
        from app.services.members import claim_invitations_for_user

        if await claim_invitations_for_user(session, user):
            await session.commit()
    except Exception:  # pragma: no cover - never block auth on invite claiming
        await session.rollback()
        logger.warning("invitation_claim_failed", user_id=str(user.id))

    return user


def _expand_allowed_roles(required: tuple[UserRole, ...]) -> set[UserRole]:
    """Expand a required-role set by the privilege hierarchy.

    A route requiring VIEWER is satisfied by viewer/agent/owner; requiring AGENT
    by agent/owner; etc. We take the *least*-privileged required role as the
    threshold and admit every role at or above it.
    """
    if not required:
        # No explicit roles => any membership is sufficient (authenticated member).
        return set(_ROLE_RANK)
    threshold = min(_ROLE_RANK[r] for r in required)
    return {role for role, rank in _ROLE_RANK.items() if rank >= threshold}


class TenantRequire:
    """Dependency factory enforcing tenant membership + role.

    Usage::

        require_agent = TenantRequire(UserRole.AGENT)

        @router.get("/console/{vendor_id}/leads")
        async def list_leads(ctx: TenantContext = Depends(require_agent)):
            ...

    The ``vendor_id`` is read from the request path. The caller's membership in
    that vendor is loaded; absence => 403, insufficient role => 403. On success
    a :class:`TenantContext` is returned.

    Note: ``vendor_id`` is pulled from ``request.path_params`` and parsed to a
    UUID here (rather than declared as a typed path parameter) deliberately —
    the module uses ``from __future__ import annotations``, and FastAPI cannot
    resolve a stringified annotation on a class-instance dependency callable.
    Reading it off the request keeps the dependency robust and self-contained.
    """

    def __init__(self, *roles: UserRole) -> None:
        self._required = roles
        self._allowed = _expand_allowed_roles(roles)

    async def __call__(
        self,
        request: Request = _RequestDep,
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
    ) -> TenantContext:
        raw_vendor_id = request.path_params.get("vendor_id")
        try:
            vendor_id = raw_vendor_id if isinstance(raw_vendor_id, UUID) else UUID(str(raw_vendor_id))
        except (ValueError, TypeError, AttributeError):
            # A malformed vendor id is a not-a-valid-tenant condition. Deny.
            logger.info("authz_bad_vendor_id", user_id=str(user.id))
            raise _forbidden()

        membership = await session.scalar(
            select(VendorMembership).where(
                VendorMembership.user_id == user.id,
                VendorMembership.vendor_id == vendor_id,
            )
        )
        if membership is None:
            # Not a member of this tenant — deny without confirming the tenant exists.
            logger.info(
                "authz_no_membership",
                user_id=str(user.id),
                vendor_id=str(vendor_id),
            )
            raise _forbidden()

        if membership.role not in self._allowed:
            logger.info(
                "authz_insufficient_role",
                user_id=str(user.id),
                vendor_id=str(vendor_id),
                role=membership.role.value,
            )
            raise _forbidden()

        return TenantContext(user=user, vendor_id=vendor_id, role=membership.role)


@dataclass(frozen=True)
class PlatformContext:
    """Authenticated + authorized context for a platform back-office route.

    Produced by :class:`PlatformRequire`. Independent of any tenant membership;
    its existence proves the caller holds at least the required platform role.
    """

    user: User
    role: PlatformRole


def _platform_forbidden() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Platform administration access required",
    )


def _expand_allowed_platform_roles(required: tuple[PlatformRole, ...]) -> set[PlatformRole]:
    """Expand required platform roles by hierarchy. Empty => any operator
    (>= support). NONE is never included."""
    effective = required or (PlatformRole.SUPPORT,)
    threshold = min(_PLATFORM_RANK[r] for r in effective)
    threshold = max(threshold, 1)  # never admit NONE (rank 0)
    return {role for role, rank in _PLATFORM_RANK.items() if rank >= threshold}


class PlatformRequire:
    """Dependency factory enforcing platform-operator authorization.

    Usage::

        require_admin = PlatformRequire(PlatformRole.ADMIN)

        @router.get("/admin/vendors")
        async def list_vendors(ctx: PlatformContext = Depends(require_admin)):
            ...

    Checks ``user.platform_role`` only — never tenant membership. Insufficient
    tier => 403. Gating every ``/api/v1/admin/**`` route with this is what keeps
    the back-office unreachable by ordinary or tenant users.
    """

    def __init__(self, *roles: PlatformRole) -> None:
        self._required = roles
        self._allowed = _expand_allowed_platform_roles(roles)

    async def __call__(self, user: User = Depends(get_current_user)) -> PlatformContext:
        if user.platform_role not in self._allowed:
            logger.info(
                "platform_authz_denied",
                user_id=str(user.id),
                role=user.platform_role.value,
            )
            raise _platform_forbidden()
        return PlatformContext(user=user, role=user.platform_role)


__all__ = [
    "TenantContext",
    "TenantRequire",
    "PlatformContext",
    "PlatformRequire",
    "get_current_user",
    "get_identity_provider",
]
