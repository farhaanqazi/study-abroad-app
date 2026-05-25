from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session


async def get_db() -> AsyncIterator[AsyncSession]:
    """Request-scoped AsyncSession.

    Thin alias over :func:`app.db.session.get_session` so route modules keep a
    single, stable import surface. Commit/rollback is the caller's (service
    layer's) responsibility.
    """
    async for session in get_session():
        yield session


def get_app_settings() -> Settings:
    return get_settings()


__all__ = ["get_db", "get_app_settings"]
