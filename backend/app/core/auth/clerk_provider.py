"""Clerk identity provider: RS256 JWT verification against a cached JWKS.

Security posture (Trail-of-Bits insecure-defaults discipline — fail CLOSED):
  * RS256 ONLY. The verifier pins ``algorithms=["RS256"]`` AND independently
    rejects any token whose header ``alg`` is not exactly ``RS256``. This blocks
    the classic JWKS algorithm-confusion attack where an attacker submits an
    ``HS256`` token signed with the (public) RSA key material as the HMAC secret.
  * The JWKS endpoint is PUBLIC. We fetch it with plain httpx and NEVER attach
    the Clerk secret key (or any Authorization header).
  * Misconfiguration (missing issuer / audience / jwks url) raises ``AuthError``
    rather than skipping a check — there is no path that accepts an unverified
    or partially verified token.
  * ``jwt.decode`` is never called without signature + iss + aud + exp/nbf
    verification enabled.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

import httpx
from jose import jwk, jwt
from jose.exceptions import JWTError
from jose.utils import base64url_decode  # noqa: F401  (re-export friendliness)

from app.core.auth.protocol import AuthClaims, AuthError
from app.core.config import Settings, get_settings

_ALLOWED_ALGORITHMS = ["RS256"]


class _JWKSCache:
    """In-memory JWKS cache keyed by ``kid`` with a TTL.

    Not shared across processes — each worker maintains its own. An ``asyncio``
    lock serializes concurrent refreshes so a burst of requests triggers at most
    one network fetch.
    """

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = max(int(ttl_seconds), 0)
        self._keys: dict[str, dict[str, Any]] = {}
        self._fetched_at: float = 0.0
        self._lock = asyncio.Lock()

    def _expired(self) -> bool:
        return (time.monotonic() - self._fetched_at) >= self._ttl

    def get(self, kid: str) -> Optional[dict[str, Any]]:
        if not self._keys or self._expired():
            return None
        return self._keys.get(kid)

    def store(self, keys: dict[str, dict[str, Any]]) -> None:
        self._keys = keys
        self._fetched_at = time.monotonic()


class ClerkProvider:
    """Verifies Clerk-issued RS256 JWTs.

    Implements the :class:`~app.core.auth.protocol.IdentityProvider` protocol.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        self._cache = _JWKSCache(self._settings.clerk_jwks_cache_ttl_seconds)

    # ------------------------------------------------------------------ config
    def _require_config(self) -> tuple[str, str, str]:
        """Return (jwks_url, issuer, audience) or fail closed if any is missing."""
        s = self._settings
        jwks_url = s.effective_clerk_jwks_url
        issuer = s.clerk_issuer
        audience = s.clerk_audience
        missing = [
            name
            for name, val in (
                ("jwks_url", jwks_url),
                ("issuer", issuer),
                ("audience", audience),
            )
            if not val
        ]
        if missing:
            # FAIL CLOSED — never accept a token when we cannot verify it.
            raise AuthError(reason=f"auth provider misconfigured: missing {', '.join(missing)}")
        return jwks_url, issuer, audience  # type: ignore[return-value]

    # -------------------------------------------------------------------- jwks
    async def _fetch_jwks(self, jwks_url: str) -> dict[str, dict[str, Any]]:
        """Fetch the public JWKS. No auth header is ever sent."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(jwks_url)  # public endpoint, no secret
                resp.raise_for_status()
                doc = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AuthError(reason=f"jwks fetch failed: {type(exc).__name__}") from exc

        keys = doc.get("keys") if isinstance(doc, dict) else None
        if not keys:
            raise AuthError(reason="jwks response had no keys")
        return {k["kid"]: k for k in keys if isinstance(k, dict) and k.get("kid")}

    async def _refresh(self, jwks_url: str) -> None:
        async with self._cache._lock:  # noqa: SLF001 — intentional internal coordination
            self._cache.store(await self._fetch_jwks(jwks_url))

    async def _get_signing_key(self, kid: str, jwks_url: str) -> dict[str, Any]:
        """Resolve the JWK for ``kid``, refetching once on a cache miss.

        Handles key rotation: an unknown ``kid`` (cache empty/expired OR a brand
        new key) forces exactly one refetch before we give up.
        """
        key = self._cache.get(kid)
        if key is not None:
            return key
        await self._refresh(jwks_url)
        key = self._cache.get(kid)
        if key is None:
            raise AuthError(reason="no signing key for token kid")
        return key

    # ------------------------------------------------------------------ verify
    async def verify(self, token: str) -> AuthClaims:
        if not token or not isinstance(token, str):
            raise AuthError(reason="empty token")

        jwks_url, issuer, audience = self._require_config()

        # Inspect the unverified header ONLY to pick the key + enforce alg.
        try:
            header = jwt.get_unverified_header(token)
        except JWTError as exc:
            raise AuthError(reason=f"malformed token header: {type(exc).__name__}") from exc

        alg = header.get("alg")
        # Defense-in-depth: reject non-RS256 before touching key material so an
        # HS256-forged token can never reach jwt.decode with a public key.
        if alg != "RS256":
            raise AuthError(reason=f"unsupported alg: {alg!r}")

        kid = header.get("kid")
        if not kid:
            raise AuthError(reason="token header missing kid")

        jwk_dict = await self._get_signing_key(kid, jwks_url)

        try:
            public_key = jwk.construct(jwk_dict, "RS256")
        except Exception as exc:  # jose raises JWKError / others on bad key data
            raise AuthError(reason=f"signing key construction failed: {type(exc).__name__}") from exc

        try:
            claims = jwt.decode(
                token,
                public_key,
                algorithms=_ALLOWED_ALGORITHMS,  # pin RS256 — no caller override
                audience=audience,
                issuer=issuer,
                options={
                    "verify_signature": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "require_exp": True,
                },
            )
        except JWTError as exc:
            # Covers expired, bad signature, iss/aud mismatch, nbf-in-future, etc.
            raise AuthError(reason=f"token verification failed: {type(exc).__name__}") from exc

        subject = claims.get("sub")
        if not subject:
            raise AuthError(reason="token missing sub claim")

        return AuthClaims(
            subject=subject,
            issuer=claims.get("iss", issuer),
            audience=audience,
            email=claims.get("email"),
            raw=claims,
        )
