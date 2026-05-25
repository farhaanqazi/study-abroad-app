"""Unit tests for the Clerk identity provider's token verification.

These exercise the *security-critical* paths with a real RSA keypair so the
signature math runs for real, while the JWKS network fetch is monkeypatched to
serve our generated public key (no network, no Clerk account needed).

Covered:
  * happy path -> AuthClaims with the right subject/email
  * kid selection across multiple keys + refetch-once on unknown kid (rotation)
  * non-RS256 algorithms rejected (HS256 algorithm-confusion + others)
  * bad issuer / audience / expired / not-yet-valid all rejected
  * misconfiguration (missing issuer/audience/jwks) fails CLOSED

Runnable two ways:
  * `pytest tests/unit/test_auth_provider.py`  (when pytest is installed)
  * `python tests/unit/test_auth_provider.py`  (standalone async runner)
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk, jwt

from app.core.auth.clerk_provider import ClerkProvider
from app.core.auth.protocol import AuthError

ISSUER = "https://clerk.test.example"
AUDIENCE = "study-abroad-app"


# --------------------------------------------------------------------------- keys
def _make_keypair(kid: str) -> tuple[str, dict[str, Any]]:
    """Return (private_pem, public_jwk_with_kid) for signing/verification."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    pub_jwk = jwk.construct(pub_pem, "RS256").to_dict()
    pub_jwk["kid"] = kid
    pub_jwk.setdefault("use", "sig")
    return priv_pem, pub_jwk


class _FakeSettings:
    """Minimal stand-in for app Settings exposing only what ClerkProvider reads."""

    def __init__(self, issuer=ISSUER, audience=AUDIENCE, jwks_url="https://jwks.test/keys"):
        self.clerk_issuer = issuer
        self.clerk_audience = audience
        self._jwks_url = jwks_url
        self.clerk_jwks_cache_ttl_seconds = 3600

    @property
    def effective_clerk_jwks_url(self):
        return self._jwks_url


def _provider_serving(jwks_keys: list[dict[str, Any]], **settings_kw) -> tuple[ClerkProvider, dict]:
    """Build a ClerkProvider whose JWKS fetch returns ``jwks_keys`` (no network).

    Returns (provider, stats) where stats["fetches"] counts network fetches so
    tests can assert the refetch-once-on-unknown-kid behavior.
    """
    provider = ClerkProvider(settings=_FakeSettings(**settings_kw))
    stats = {"fetches": 0}

    async def fake_fetch(jwks_url: str):
        stats["fetches"] += 1
        return {k["kid"]: k for k in jwks_keys}

    provider._fetch_jwks = fake_fetch  # type: ignore[assignment]
    return provider, stats


def _token(priv_pem, kid, *, sub="user_abc", iss=ISSUER, aud=AUDIENCE, alg="RS256", extra=None):
    claims: dict[str, Any] = {
        "sub": sub,
        "iss": iss,
        "aud": aud,
        "exp": int(time.time()) + 3600,
        "nbf": int(time.time()) - 5,
        "email": "user@example.com",
    }
    if extra:
        claims.update(extra)
    return jwt.encode(claims, priv_pem, algorithm=alg, headers={"kid": kid})


# --------------------------------------------------------------------------- tests
async def test_happy_path_returns_claims():
    priv, pub = _make_keypair("k1")
    provider, _ = _provider_serving([pub])
    claims = await provider.verify(_token(priv, "k1"))
    assert claims.subject == "user_abc"
    assert claims.clerk_id == "user_abc"
    assert claims.email == "user@example.com"
    assert claims.issuer == ISSUER


async def test_kid_selection_among_multiple_keys():
    priv1, pub1 = _make_keypair("k1")
    priv2, pub2 = _make_keypair("k2")
    provider, _ = _provider_serving([pub1, pub2])
    # A token signed by key 2 must verify against key 2 (correct kid selection),
    # not key 1.
    claims = await provider.verify(_token(priv2, "k2"))
    assert claims.subject == "user_abc"


async def test_refetch_once_on_unknown_kid():
    # Cache initially empty; first verify forces a fetch. Then rotate in a new
    # key — an unknown kid must trigger exactly one refetch and then succeed.
    priv1, pub1 = _make_keypair("k1")
    priv2, pub2 = _make_keypair("k2")
    provider = ClerkProvider(settings=_FakeSettings())
    served = {"keys": [pub1]}
    stats = {"fetches": 0}

    async def fake_fetch(jwks_url: str):
        stats["fetches"] += 1
        return {k["kid"]: k for k in served["keys"]}

    provider._fetch_jwks = fake_fetch  # type: ignore[assignment]

    # k1 present -> 1 fetch
    await provider.verify(_token(priv1, "k1"))
    assert stats["fetches"] == 1

    # Rotate: server now also serves k2; a k2 token is unknown in cache -> refetch
    served["keys"] = [pub1, pub2]
    await provider.verify(_token(priv2, "k2"))
    assert stats["fetches"] == 2


async def test_unknown_kid_after_refetch_rejected():
    priv1, pub1 = _make_keypair("k1")
    provider, stats = _provider_serving([pub1])
    # Token claims kid k9 which the JWKS never serves -> refetch once then 401.
    bad = _token(priv1, "k9")
    try:
        await provider.verify(bad)
        raise AssertionError("expected AuthError for unknown kid")
    except AuthError:
        pass
    assert stats["fetches"] == 1  # exactly one refetch attempt


async def test_non_rs256_rejected():
    # Algorithm-confusion: attacker signs HS256 using the public key bytes as the
    # HMAC secret, hoping the verifier accepts it. Must be rejected at the header.
    priv, pub = _make_keypair("k1")
    provider, _ = _provider_serving([pub])
    hs_token = jwt.encode(
        {"sub": "evil", "iss": ISSUER, "aud": AUDIENCE, "exp": int(time.time()) + 99},
        "any-secret",
        algorithm="HS256",
        headers={"kid": "k1"},
    )
    try:
        await provider.verify(hs_token)
        raise AssertionError("expected AuthError for HS256 token")
    except AuthError:
        pass


async def test_wrong_issuer_rejected():
    priv, pub = _make_keypair("k1")
    provider, _ = _provider_serving([pub])
    try:
        await provider.verify(_token(priv, "k1", iss="https://evil.example"))
        raise AssertionError("expected AuthError for bad issuer")
    except AuthError:
        pass


async def test_wrong_audience_rejected():
    priv, pub = _make_keypair("k1")
    provider, _ = _provider_serving([pub])
    try:
        await provider.verify(_token(priv, "k1", aud="some-other-app"))
        raise AssertionError("expected AuthError for bad audience")
    except AuthError:
        pass


async def test_expired_rejected():
    priv, pub = _make_keypair("k1")
    provider, _ = _provider_serving([pub])
    try:
        await provider.verify(_token(priv, "k1", extra={"exp": int(time.time()) - 10}))
        raise AssertionError("expected AuthError for expired token")
    except AuthError:
        pass


async def test_not_yet_valid_rejected():
    priv, pub = _make_keypair("k1")
    provider, _ = _provider_serving([pub])
    try:
        await provider.verify(_token(priv, "k1", extra={"nbf": int(time.time()) + 600}))
        raise AssertionError("expected AuthError for nbf-in-future token")
    except AuthError:
        pass


async def test_wrong_signing_key_rejected():
    # Signed with key1, but JWKS only serves key2 under the same kid -> sig fail.
    priv1, _ = _make_keypair("k1")
    _, pub2 = _make_keypair("k1")  # different key material, same kid
    provider, _ = _provider_serving([pub2])
    try:
        await provider.verify(_token(priv1, "k1"))
        raise AssertionError("expected AuthError for bad signature")
    except AuthError:
        pass


async def test_misconfiguration_fails_closed():
    priv, pub = _make_keypair("k1")
    # Missing issuer => must raise before any verification, never accept.
    provider, _ = _provider_serving([pub], issuer=None)
    try:
        await provider.verify(_token(priv, "k1"))
        raise AssertionError("expected AuthError when issuer missing")
    except AuthError:
        pass

    provider2, _ = _provider_serving([pub], audience=None)
    try:
        await provider2.verify(_token(priv, "k1"))
        raise AssertionError("expected AuthError when audience missing")
    except AuthError:
        pass

    provider3, _ = _provider_serving([pub], jwks_url=None)
    try:
        await provider3.verify(_token(priv, "k1"))
        raise AssertionError("expected AuthError when jwks url missing")
    except AuthError:
        pass


async def test_malformed_token_rejected():
    priv, pub = _make_keypair("k1")
    provider, _ = _provider_serving([pub])
    for bad in ("", "not-a-jwt", "a.b.c"):
        try:
            await provider.verify(bad)
            raise AssertionError(f"expected AuthError for malformed token {bad!r}")
        except AuthError:
            pass


_TESTS = [
    test_happy_path_returns_claims,
    test_kid_selection_among_multiple_keys,
    test_refetch_once_on_unknown_kid,
    test_unknown_kid_after_refetch_rejected,
    test_non_rs256_rejected,
    test_wrong_issuer_rejected,
    test_wrong_audience_rejected,
    test_expired_rejected,
    test_not_yet_valid_rejected,
    test_wrong_signing_key_rejected,
    test_misconfiguration_fails_closed,
    test_malformed_token_rejected,
]


def _run_all() -> int:
    failures = 0
    for t in _TESTS:
        try:
            asyncio.run(t())
            print(f"PASS {t.__name__}")
        except Exception as exc:  # noqa: BLE001 - standalone runner
            failures += 1
            print(f"FAIL {t.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(_TESTS) - failures}/{len(_TESTS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
