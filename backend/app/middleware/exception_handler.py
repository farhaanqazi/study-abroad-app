"""
Global exception handling — replaces Starlette's ServerErrorMiddleware.

This is the LAST middleware in the chain. It catches ALL exceptions that
escape the rest of the stack, including ExceptionGroups from
BaseHTTPMiddleware's task group.

Registered via `app.add_exception_handler` or by replacing Starlette's
ServerErrorMiddleware at app construction time.
"""

from __future__ import annotations

from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

from app.utils.logger import app_logger


def build_exception_handler() -> Any:
    """
    Build a callable exception handler that replaces Starlette's default.

    Returns an async function: (request, exc) -> Response
    
    Tracebacks are logged via exc_info=True. The error.log handler will
    render the full traceback, while app.log's CompactFormatter suppresses it.
    """
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")

        error_context: dict[str, Any] = {
            "event": "unhandled_exception",
            "request_id": request_id,
            "path": str(request.url.path),
            "method": request.method,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }

        if request.query_params:
            error_context["query_params"] = str(request.query_params)
        if request.client:
            error_context["client_host"] = request.client.host

        app_logger.error(
            f"Unhandled exception: {type(exc).__name__}: {exc}",
            exc_info=True,
            **error_context,
        )

        from app.core.config import get_settings
        settings = get_settings()

        if settings.environment == "production":
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "request_id": request_id,
                }
            )

        return JSONResponse(
            status_code=500,
            content={
                "detail": f"Internal server error: {type(exc).__name__}",
                "message": str(exc),
                "request_id": request_id,
            }
        )

    return handler
