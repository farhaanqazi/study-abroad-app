"""Outbound side-effect delivery for the transactional outbox.

These functions perform the *actual* network IO (SMTP, HTTP webhooks). They are
called only from the worker's outbox processor, never from request handlers or
the LeadCaptureService — the service merely records intent.

Contract: both senders **raise on failure**. The processor relies on the raised
exception to record a failure and schedule a retry. They must NOT swallow
errors and return falsy values, or events would silently never deliver.

Blocking IO (stdlib ``smtplib``) is offloaded with ``asyncio.to_thread`` so the
worker's event loop is never blocked while a mail server hangs.
"""

from __future__ import annotations

import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import httpx

from app.core.config import Settings, get_settings
from app.core.observability import get_logger

logger = get_logger(__name__)

# Default network ceilings — kept tight so a hung peer reschedules rather than
# pinning a worker slot.
WEBHOOK_TIMEOUT_SECONDS = 10.0
SMTP_TIMEOUT_SECONDS = 20.0


class SenderConfigError(RuntimeError):
    """Raised when a sender is invoked but its transport is not configured.

    Fail loud, not silent: a misconfigured SMTP server must surface as an error
    the processor records (and ultimately a FAILED event), not a quiet no-op
    that drops every notification on the floor.
    """


class SenderDeliveryError(RuntimeError):
    """Raised when delivery is attempted but the remote rejects/errors."""


def _smtp_enabled(settings: Settings) -> bool:
    return bool(settings.email_smtp_host and settings.email_smtp_user and settings.email_smtp_password)


def _send_email_blocking(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    sender: str,
    to_email: str,
    subject: str,
    html_body: str,
) -> None:
    """Blocking SMTP send — runs inside a worker thread, never the event loop."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender or user
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT_SECONDS) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)


async def send_email(
    *,
    to_email: str,
    subject: str,
    html_body: str,
    settings: Optional[Settings] = None,
) -> None:
    """Send an HTML email via SMTP, offloaded to a worker thread.

    Raises ``SenderConfigError`` if SMTP is not configured, and
    ``SenderDeliveryError`` if the SMTP server rejects the message.
    """
    settings = settings or get_settings()

    if not _smtp_enabled(settings):
        raise SenderConfigError(
            "SMTP is not configured (EMAIL_SMTP_HOST/USER/PASSWORD). "
            "Cannot deliver email notification."
        )
    if not to_email:
        raise SenderConfigError("send_email called with empty recipient address")

    try:
        await asyncio.to_thread(
            _send_email_blocking,
            host=settings.email_smtp_host,
            port=settings.email_smtp_port,
            user=settings.email_smtp_user,
            password=settings.email_smtp_password,
            sender=settings.email_from,
            to_email=to_email,
            subject=subject,
            html_body=html_body,
        )
    except smtplib.SMTPException as exc:
        logger.warning("email_send_failed", to=to_email, error=str(exc))
        raise SenderDeliveryError(f"SMTP delivery failed: {exc}") from exc

    logger.info("email_sent", to=to_email, subject=subject)


async def send_webhook(
    *,
    url: str,
    payload: dict,
    headers: Optional[dict[str, str]] = None,
    timeout: float = WEBHOOK_TIMEOUT_SECONDS,
) -> None:
    """POST a JSON payload to a webhook URL via httpx (async).

    Raises ``SenderConfigError`` if no URL is provided, and
    ``SenderDeliveryError`` for connection errors or non-2xx responses.
    """
    if not url:
        raise SenderConfigError("send_webhook called with empty URL")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=headers or {})
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "webhook_non_2xx",
            url=url,
            status=exc.response.status_code,
        )
        raise SenderDeliveryError(
            f"Webhook {url} returned {exc.response.status_code}"
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning("webhook_transport_error", url=url, error=str(exc))
        raise SenderDeliveryError(f"Webhook {url} transport error: {exc}") from exc

    logger.info("webhook_sent", url=url)
