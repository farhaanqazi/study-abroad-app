"""Provider-agnostic authentication layer.

`protocol` defines the IdP-neutral contract (``AuthClaims`` + ``IdentityProvider``);
``clerk_provider`` is the concrete Clerk/JWKS implementation. Nothing here knows
about FastAPI — request wiring lives in ``app.api.dependencies.auth``.
"""

from __future__ import annotations

from app.core.auth.protocol import AuthClaims, AuthError, IdentityProvider

__all__ = ["AuthClaims", "AuthError", "IdentityProvider"]
