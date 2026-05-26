import time

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

from app.core.observability import get_logger

logger = get_logger("app.request")


class RequestTimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1_000

        # request_id is set on scope state by the inner RequestIDMiddleware;
        # read it explicitly since BaseHTTPMiddleware runs outside the contextvar
        # scope where it's bound.
        logger.info(
            "request_completed",
            request_id=getattr(request.state, "request_id", None),
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        return response
