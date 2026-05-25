"""
Rate limiting middleware using slowapi.

Protects against brute-force, abuse, and DDoS.
Applied to critical endpoints: auth, webhooks, user creation.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared limiter instance — used by SlowAPIMiddleware and exception handler
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
    strategy="fixed-window",
)


def get_limiter() -> Limiter:
    """Return the shared limiter instance."""
    return limiter
