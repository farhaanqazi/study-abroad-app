"""
Request ID middleware — pure ASGI implementation.

Avoids BaseHTTPMiddleware to prevent Starlette's ExceptionGroup bug.
Adds a unique request ID to every request/response cycle.
"""

from __future__ import annotations

import re
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.utils.logger import set_request_id_context


_HEX_RE = re.compile(r"[a-fA-F0-9]")


def _normalize_request_id(raw_value: str | None) -> str:
    if raw_value:
        cleaned = "".join(_HEX_RE.findall(raw_value))
        if len(cleaned) >= 8:
            return cleaned[:8].lower()
    return uuid4().hex[:8]


class RequestIDMiddleware:
    """
    Pure ASGI middleware that adds X-Request-ID to every request.

    Does NOT use BaseHTTPMiddleware to avoid Starlette's ExceptionGroup
    task group bug.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _normalize_request_id(
            scope.get("headers", [])
            and next(
                (v.decode() for k, v in scope["headers"] if k.lower() == b"x-request-id"),
                None,
            )
        )

        # Store in scope state for access in endpoints/logging
        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["request_id"] = request_id

        # Set in contextvar for automatic log injection
        set_request_id_context(request_id)

        # Intercept response messages to add X-Request-ID header
        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_request_id)
