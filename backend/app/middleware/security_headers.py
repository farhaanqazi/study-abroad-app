"""
Security headers middleware.

Adds OWASP-recommended HTTP security headers to every response:
- Strict-Transport-Security (HSTS)
- X-Content-Type-Options
- X-Frame-Options
- Content-Security-Policy
- Referrer-Policy
- Permissions-Policy
"""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class SecurityHeadersMiddleware:
    """Pure ASGI middleware that adds security headers to every HTTP response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Security headers applied to every response
        security_headers: list[tuple[bytes, bytes]] = [
            # Prevent MIME-type sniffing
            (b"x-content-type-options", b"nosniff"),
            # Prevent clickjacking
            (b"x-frame-options", b"DENY"),
            # Control referrer information
            (b"referrer-policy", b"strict-origin-when-cross-origin"),
            # Restrict browser features
            (
                b"permissions-policy",
                b"camera=(), microphone=(), geolocation=()",
            ),
            # Content Security Policy — restrictive default
            (
                b"content-security-policy",
                b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
            ),
        ]

        # HSTS only in production (or non-development)
        from app.core.config import get_settings
        settings = get_settings()
        if settings.environment != "development":
            security_headers.append(
                (
                    b"strict-transport-security",
                    b"max-age=31536000; includeSubDomains",
                )
            )

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                existing_headers = list(message.get("headers", []))
                # Don't overwrite existing headers
                for header_name, header_value in security_headers:
                    if not any(h[0].lower() == header_name for h in existing_headers):
                        existing_headers.append((header_name, header_value))
                message = {**message, "headers": existing_headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)
