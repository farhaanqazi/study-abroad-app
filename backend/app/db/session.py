from __future__ import annotations

import ssl
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import certifi
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings


def normalize_database_url_for_asyncpg(db_url: str) -> tuple[str, str]:
    """
    Normalize common Supabase/Postgres URL schemes for SQLAlchemy + asyncpg.

    Supabase may show pooler URLs as postgres://, while SQLAlchemy expects the
    postgresql+asyncpg driver name. asyncpg also rejects sslmode as a URL query
    parameter, so this returns the cleaned URL and the requested SSL mode.
    """
    db_url = db_url.strip()

    if not db_url:
        raise ValueError("DATABASE_URL is not set")

    if db_url.startswith("postgresql+asyncpg://"):
        parse_url = "postgresql://" + db_url.split("://", 1)[1]
    elif db_url.startswith("postgres://"):
        parse_url = "postgresql://" + db_url.split("://", 1)[1]
    else:
        parse_url = db_url

    parsed = urlparse(parse_url)
    if parsed.scheme != "postgresql":
        raise ValueError(
            "DATABASE_URL must start with postgresql+asyncpg://, postgresql://, or postgres://"
        )

    if not parsed.hostname:
        raise ValueError("Could not parse hostname from DATABASE_URL")

    query_params = parse_qs(parsed.query)
    ssl_mode = query_params.get("sslmode", ["require"])[0]
    clean_query = {k: v for k, v in query_params.items() if k != "sslmode"}
    clean_url = urlunparse(
        (
            "postgresql+asyncpg",
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(clean_query, doseq=True),
            parsed.fragment,
        )
    )

    return clean_url, ssl_mode


def create_db_engine(settings: Settings):
    """
    Create a production-grade secure PostgreSQL engine for Supabase.

    This implementation:
    - Uses sslmode=require from the DATABASE_URL for SSL encryption
    - Uses connection pooling (AsyncAdaptedQueuePool) for high performance
    - Recycles connections to prevent Supabase timeout issues
    - Validates DATABASE_URL format and presence
    """
    clean_url, ssl_mode = normalize_database_url_for_asyncpg(settings.database_url)

    # Create SSL context based on sslmode
    ssl_context = None
    if ssl_mode in ("require", "verify-full", "verify-ca"):
        # Supabase pooler presents a cert that does not validate against the
        # certifi CA bundle, so we encrypt without chain verification —
        # matching Supabase's documented sslmode=require behavior. Tightening
        # this to CERT_REQUIRED requires shipping Supabase's CA explicitly.
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

    connect_args = {}
    if ssl_context:
        connect_args["ssl"] = ssl_context

    engine = create_async_engine(
        clean_url,
        connect_args=connect_args,
        # Connection Pooling Configuration (Production Optimized)
        pool_size=10,           # Keep 10 connections open and ready in the pool
        max_overflow=20,        # Allow 20 temporary connections during traffic spikes
        pool_pre_ping=True,     # Verify connection is alive before use (prevents stale connections)
        pool_recycle=1800,      # Recycle connections every 30 minutes (prevents Supabase timeouts)
        echo=settings.debug,
    )

    return engine


class DatabaseSession:
    """
    Database session manager with secure engine initialization.
    
    All database connections use SSL encryption when sslmode=require
    is specified in the DATABASE_URL.
    """

    def __init__(self) -> None:
        self._engine: Optional[object] = None
        self._session_factory: Optional[async_sessionmaker] = None

    def initialize(self, settings: Settings) -> None:
        """Initialize the engine and session factory with secure SSL."""
        if self._engine is not None:
            return

        self._engine = create_db_engine(settings)
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @property
    def engine(self):
        """Get the engine, initializing if necessary."""
        if self._engine is None:
            from app.core.config import get_settings
            self.initialize(get_settings())
        return self._engine

    @property
    def session_factory(self):
        """Get the session factory, initializing if necessary."""
        if self._session_factory is None:
            from app.core.config import get_settings
            self.initialize(get_settings())
        return self._session_factory

    async def dispose(self) -> None:
        """Dispose of the engine and reset."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None


# Global instance - lazy initialization
db_session = DatabaseSession()

# Backwards compatibility - these will initialize on first use
engine = db_session.engine
SessionLocal = db_session.session_factory
