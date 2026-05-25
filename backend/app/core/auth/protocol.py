"""Provider-agnostic auth contract.

This module is intentionally free of any IdP SDK (no Clerk, no jose, no httpx) so
that the rest of the application can depend on an abstract identity contract and
swap providers without touching call sites.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable


class AuthError(Exception):
    """Raised whenever a bearer token cannot be trusted.

    This is the *only* error type the provider layer is allowed to surface for
    authentication problems. It is deliberately coarse and message-light: callers
    map it to HTTP 401 and must never leak the underlying reason (key id, claim
    mismatch, network error) to the client. The optional ``reason`` is for
    server-side structured logging only.
    """

    def __init__(self, message: str = "authentication failed", *, reason: Optional[str] = None) -> None:
        super().__init__(message)
        self.reason = reason or message


@dataclass(frozen=True)
class AuthClaims:
    """Verified identity extracted from a token.

    Construct this ONLY after a provider has fully validated signature + claims.
    The presence of an ``AuthClaims`` instance is itself the proof of trust.
    """

    # The IdP subject — for Clerk this is the stable user id we persist as
    # ``User.clerk_id``.
    subject: str
    issuer: str
    audience: Optional[str] = None
    email: Optional[str] = None
    # Full set of validated claims, for callers that need provider-specific fields.
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def clerk_id(self) -> str:
        """Alias for :attr:`subject` — the persisted external identity key."""
        return self.subject


@runtime_checkable
class IdentityProvider(Protocol):
    """An external identity provider that can verify a bearer token.

    Implementations MUST fail closed: any verification problem (bad signature,
    wrong issuer/audience, expired, misconfiguration) raises :class:`AuthError`.
    A successful return is a guarantee the token is fully trustworthy.
    """

    async def verify(self, token: str) -> AuthClaims:  # pragma: no cover - protocol
        ...
