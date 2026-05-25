import time
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

from app.utils.logger import app_logger


class RequestTimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()

        response = await call_next(request)

        duration = time.perf_counter() - start
        duration_ms = duration * 1_000

        app_logger.info(
            "Request completed",
            event="request_latency",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=f"{duration_ms:.2f}ms",
        )

        return response
