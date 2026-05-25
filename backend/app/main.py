from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette import status
from starlette.middleware.errors import ServerErrorMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.db.session import db_session
from app.middleware.exception_handler import build_exception_handler
from app.middleware.rate_limiter import limiter as shared_limiter
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.request_timing import RequestTimingMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.redis.client import build_redis_client
from app.utils.logger import app_logger


# Configure logging before anything else
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for proper resource initialization and cleanup.
    
    Resources are initialized in order and cleaned up in reverse order on shutdown.
    If any initialization fails, already-initialized resources are properly cleaned up.
    """
    settings = get_settings()
    redis_client = None
    initialized_resources: list[str] = []

    try:
        # Initialize resources in order
        redis_client = build_redis_client(settings.redis_url)
        initialized_resources.append("redis")

        # Initialize database session
        db_session.initialize(settings)
        initialized_resources.append("database")

        # Store in app state
        app.state.settings = settings
        app.state.redis_client = redis_client

        # Log startup information
        logger.info(
            f"Application started: {settings.app_name} (env={settings.environment}, debug={settings.debug})"
        )

        yield

    except Exception as e:
        logger.error(f"Startup failed: {e}")
        # Clean up any initialized resources on failure
        await _cleanup_resources(
            redis_client=redis_client if "redis" in initialized_resources else None,
            cleanup_db="database" in initialized_resources,
        )
        raise
    else:
        # Clean up on normal shutdown
        await _cleanup_resources(
            redis_client=redis_client,
            cleanup_db=True,
        )


async def _cleanup_resources(
    redis_client: Any | None = None,
    cleanup_db: bool = False,
) -> None:
    """Clean up application resources in reverse order."""
    errors: list[str] = []

    if redis_client is not None:
        try:
            await redis_client.aclose()
        except Exception as e:
            errors.append(f"Redis client: {e}")
    
    if cleanup_db:
        try:
            await db_session.dispose()
        except Exception as e:
            errors.append(f"Database: {e}")
    
    if errors:
        logger.warning(f"Cleanup errors: {'; '.join(errors)}")


# Get settings early for app configuration
settings = get_settings()

# Configure CORS with environment-based origins
if settings.environment == "development":
    cors_origins = ["*"]
else:
    cors_origins = settings.cors_origins_list

app = FastAPI(
    title=settings.app_name,
    description="Multi-tenant study-abroad agency platform: public lead capture + tenant-scoped management console.",
    version="0.1.0",
    openapi_url=f"{settings.api_prefix}/openapi.json",
    debug=settings.debug,
    lifespan=lifespan,
)

# === REPLACE Starlette's ServerErrorMiddleware ===
# This is the LAST middleware in the chain. It catches ALL exceptions that
# escape the rest of the stack, including ExceptionGroups from middleware.
app.add_middleware(
    ServerErrorMiddleware,
    handler=build_exception_handler(),
    debug=settings.debug,
)

# === MIDDLEWARE REGISTRATION ORDER (outside-in) ===
# 1. Security Headers (applied to all responses)
app.add_middleware(SecurityHeadersMiddleware)
# 2. Request ID (pure ASGI — avoids Starlette's ExceptionGroup bug)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(RequestTimingMiddleware)
# 3. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


# ============================================================================
# Rate Limiting
# ============================================================================
app.state.limiter = shared_limiter  # Required by slowapi exception handler
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# Per-endpoint rate limits are applied via decorators in individual routers.
# No global middleware needed — each endpoint defines its own limits.


# ============================================================================
# Exception Handlers (route-level only)
# ============================================================================
# Global exceptions are caught by ServerErrorMiddleware above.

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle FastAPI HTTPExceptions (4xx errors).
    Logs auth failures and permission denials for security auditing.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    # Only log 4xx errors that indicate security events (not routine 404s)
    if exc.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}:
        event_type = "auth_failure" if exc.status_code == 401 else "authorization_failure"
        app_logger.warn(
            f"HTTP {exc.status_code}: {exc.detail}",
            event=event_type,
            request_id=request_id,
            path=str(request.url.path),
            method=request.method,
            status_code=exc.status_code,
            detail=exc.detail,
        )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "request_id": request_id},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle request validation errors (malformed JSON, missing fields, bad types).
    Logs structured summary without dumping full request body.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    app_logger.warn(
        "Request validation failed",
        event="validation_error",
        request_id=request_id,
        path=str(request.url.path),
        method=request.method,
        error_count=len(exc.errors()),
        errors=[{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()],
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        # jsonable_encoder: Pydantic v2 puts the raw ValueError from custom
        # validators in each error's ctx, which is not JSON-serializable.
        content={"detail": jsonable_encoder(exc.errors()), "request_id": request_id},
    )


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """
    Health check endpoint.
    
    Returns application status and version information.
    """
    return {"status": "ok", "version": "1.0.0"}


@app.get("/health/ready", tags=["health"])
async def readiness_check() -> dict:
    """
    Readiness check endpoint.
    
    Verifies that all required services (database, Redis) are available.
    """
    from sqlalchemy import text
    
    status = {"status": "ok", "services": {}}
    
    # Check database
    try:
        async with db_session.session_factory() as session:
            await session.execute(text("SELECT 1"))
        status["services"]["database"] = "ok"
    except Exception as e:
        status["services"]["database"] = f"error: {e}"
        status["status"] = "degraded"
    
    # Check Redis
    try:
        redis_client = app.state.redis_client
        await redis_client.ping()
        status["services"]["redis"] = "ok"
    except Exception as e:
        status["services"]["redis"] = f"error: {e}"
        status["status"] = "degraded"
    
    return status


if settings.environment != "production":
    @app.get("/debug/db-url", tags=["debug"])
    async def debug_db_url() -> dict:
        """Debug endpoint to verify database URL configuration."""
        from app.core.config import get_settings
        settings = get_settings()
        # Mask password in URL for security
        db_url = settings.database_url
        if "@" in db_url:
            parts = db_url.split("@")
            if "://" in parts[0]:
                protocol, creds = parts[0].split("://", 1)
                if ":" in creds:
                    username = creds.split(":")[0]
                    masked = f"{protocol}://{username}:***@{parts[1]}"
                else:
                    masked = f"{protocol}://***@{parts[1]}"
            else:
                masked = "***"
        else:
            masked = "***"
        return {"db_url_masked": masked}


# ============================================================================
# SPA Fallback — serve the built React frontend for all non-API routes.
# Only activated when `frontend/dist` exists (i.e. after `npm run build`).
# In development the Vite dev server handles routing itself.
# ============================================================================
_frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _frontend_dist.is_dir():
    # Serve hashed asset bundles (JS, CSS, images) under /assets
    _assets_dir = _frontend_dist / "assets"
    if _assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="spa-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _spa_fallback(full_path: str) -> FileResponse:
        """Serve built frontend assets directly and fall back to index.html for SPA routes."""
        requested_path = (_frontend_dist / full_path).resolve()
        if requested_path.is_file() and requested_path.is_relative_to(_frontend_dist):
            return FileResponse(str(requested_path))
        return FileResponse(str(_frontend_dist / "index.html"))
