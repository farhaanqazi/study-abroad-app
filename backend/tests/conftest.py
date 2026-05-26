"""Shared pytest fixtures.

The app holds a process-wide lazily-initialized async engine (``db_session``).
pytest-asyncio runs each ``async def`` test in its own event loop, so an engine
built on one test's loop cannot be reused on the next (asyncpg connections are
loop-bound). This autouse fixture forces the engine to be rebuilt on each test's
current loop, eliminating "attached to a different loop" / "event loop is closed"
errors.

Requires DATABASE_URL to point at a disposable local DB (never production).
"""

from __future__ import annotations

import pytest

from app.db.session import db_session


@pytest.fixture(autouse=True)
def _fresh_db_engine_per_test():
    db_session._engine = None
    db_session._session_factory = None
    yield
    db_session._engine = None
    db_session._session_factory = None
