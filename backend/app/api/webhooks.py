from __future__ import annotations

import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import get_app_settings, get_conversation_service, get_db
from app.core.config import Settings
from app.schemas.messages import ProcessResult
from app.services.conversation_service import ConversationService
from app.services.webhook_service import WebhookService
from app.utils.logger import app_logger

# Per-webhook rate limit: 60 per minute per IP (covers burst from Telegram/WhatsApp)
_webhook_limiter = Limiter(key_func=get_remote_address, default_limits=["60 per minute"])

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/whatsapp/{vendor_slug}")
async def verify_whatsapp_webhook(
    request: Request,
    vendor_slug: str,
    mode: str | None = Query(default=None, alias="hub.mode"),
    verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
    settings: Settings = Depends(get_app_settings),
) -> str:
    del vendor_slug
    if mode == "subscribe" and verify_token == settings.whatsapp_verify_token and challenge:
        app_logger.info(
            "WhatsApp webhook verified",
            event="webhook_verified",
            channel="whatsapp",
        )
        return challenge
    app_logger.warn(
        "WhatsApp webhook verification failed",
        event="webhook_verification_failure",
        channel="whatsapp",
        mode=mode,
        has_token=bool(verify_token),
    )
    raise HTTPException(status_code=403, detail="Webhook verification failed.")


@router.post("/whatsapp/{vendor_slug}")
async def receive_whatsapp_webhook(
    request: Request,
    vendor_slug: str,
    db=Depends(get_db),
    conversation_service: ConversationService = Depends(get_conversation_service),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    # Read raw body for signature verification
    raw_body = await request.body()
    
    # Verify WhatsApp webhook signature (HMAC-SHA256)
    x_hub_signature = request.headers.get("X-Hub-Signature-256", "")
    if settings.whatsapp_access_token:
        if not x_hub_signature:
            app_logger.warn(
                "WhatsApp webhook signature missing",
                event="webhook_auth_failure",
                channel="whatsapp",
                vendor_slug=vendor_slug,
            )
            raise HTTPException(status_code=403, detail="Missing webhook signature")
            
        expected_signature = "sha256=" + hmac.new(
            settings.whatsapp_access_token.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(x_hub_signature, expected_signature):
            app_logger.warn(
                "WhatsApp webhook signature mismatch",
                event="webhook_auth_failure",
                channel="whatsapp",
                vendor_slug=vendor_slug,
            )
            raise HTTPException(status_code=403, detail="Invalid webhook signature")

    # Parse JSON body manually (raw body already consumed)
    import json
    try:
        payload = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    app_logger.info(
        "WhatsApp webhook received",
        event="webhook_received",
        channel="whatsapp",
        vendor_slug=vendor_slug,
        message_count=len(payload.get("entry", [])),
    )
    try:
        normalized_messages = WebhookService.normalize_whatsapp_update(vendor_slug, payload)
        results: list[ProcessResult] = []
        for message in normalized_messages:
            results.append(await conversation_service.handle_inbound(message))
        app_logger.info(
            "WhatsApp webhook processed",
            event="webhook_processed",
            channel="whatsapp",
            vendor_slug=vendor_slug,
            processed_count=len(results),
        )
        return {"processed": len(results), "results": [result.model_dump() for result in results]}
    except Exception as e:
        app_logger.error(
            "WhatsApp webhook failed",
            event="webhook_error",
            channel="whatsapp",
            vendor_slug=vendor_slug,
            error_type=type(e).__name__,
            error_message=str(e),
            exc_info=True,
        )
        raise


@router.post("/telegram/{vendor_slug}")
async def receive_telegram_webhook(
    request: Request,
    vendor_slug: str,
    db=Depends(get_db),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> dict:
    # Resolve per-vendor bot token from DB — no global fallback
    from sqlalchemy import select as sa_select
    from app.db.models.vendor import Vendor, VendorChannel
    from app.core.enums import ChannelType

    vendor_result = await db.execute(
        sa_select(Vendor).where(Vendor.slug == vendor_slug)
    )
    vendor = vendor_result.scalar_one_or_none()

    if not vendor:
        raise HTTPException(status_code=404, detail=f"Vendor '{vendor_slug}' not found.")

    ch_result = await db.execute(
        sa_select(VendorChannel).where(
            VendorChannel.vendor_id == vendor.id,
            VendorChannel.channel == ChannelType.TELEGRAM,
        )
    )
    channel = ch_result.scalar_one_or_none()
    bot_token = (channel.provider_config or {}).get("bot_token") if channel else None

    if not bot_token:
        app_logger.error(
            "Telegram bot token not configured for vendor",
            event="webhook_config_error",
            channel="telegram",
            vendor_slug=vendor_slug,
        )
        raise HTTPException(status_code=500, detail=f"Telegram channel not configured for vendor '{vendor_slug}'.")

    # Verify Telegram webhook secret token
    # secret_token was set as bot_token.replace(":", "_") during setWebhook
    secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    expected_secret = bot_token.replace(":", "_")

    if secret_token != expected_secret:
        app_logger.warn(
            "Telegram webhook secret mismatch",
            event="webhook_auth_failure",
            channel="telegram",
            vendor_slug=vendor_slug,
            has_secret=bool(secret_token),
        )
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    # Read and parse raw body
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    app_logger.info(
        "Telegram webhook received",
        event="webhook_received",
        channel="telegram",
        vendor_slug=vendor_slug,
        message_count=len(payload.get("entry", [])),
    )
    try:
        normalized_messages = WebhookService.normalize_telegram_update(vendor_slug, payload)
        results: list[ProcessResult] = []
        for message in normalized_messages:
            results.append(await conversation_service.handle_inbound(message))
        app_logger.info(
            "Telegram webhook processed",
            event="webhook_processed",
            channel="telegram",
            vendor_slug=vendor_slug,
            processed_count=len(results),
        )
        return {"processed": len(results), "results": [result.model_dump() for result in results]}
    except Exception as e:
        app_logger.error(
            "Telegram webhook failed",
            event="webhook_error",
            channel="telegram",
            vendor_slug=vendor_slug,
            error_type=type(e).__name__,
            error_message=str(e),
            exc_info=True,
        )
        raise
