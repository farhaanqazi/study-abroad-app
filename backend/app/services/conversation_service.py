from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.llm.service import LLMService
from app.messaging.dispatcher import MessageDispatcher
from app.redis.state_store import RedisStateStore
from app.schemas.messages import NormalizedInboundMessage, OutboundInstruction, ProcessResult
from app.schemas.state import ConversationState
from app.services.email_service import EmailService
from app.services.tenant_service import TenantService
from app.utils.logger import app_logger


class ConversationService:
    """Minimal echo orchestrator.

    Inbound webhook -> tenant lookup -> Redis state -> echo dispatch.
    The vendor flow engine and intent handlers have been quarantined to
    _archive/vendor/. Domain handlers should be reintroduced by extending
    handle_inbound (or routing to a new dispatcher) — not by reviving
    the legacy flows/engine.py.
    """

    def __init__(
        self,
        db: AsyncSession,
        settings: Settings,
        state_store: RedisStateStore,
        llm_service: LLMService,
        dispatcher: MessageDispatcher,
        email_service: EmailService | None = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.state_store = state_store
        self.llm_service = llm_service
        self.dispatcher = dispatcher
        self.email_service = email_service
        self.tenant_service = TenantService(db)

    async def handle_inbound(self, inbound: NormalizedInboundMessage) -> ProcessResult:
        app_logger.info(
            "Inbound message received",
            event="inbound_received",
            channel=inbound.channel.value,
            tenant_slug=inbound.vendor_slug,
            external_user_id=inbound.external_user_id,
            has_text=bool(inbound.text),
        )

        if inbound.provider_message_id:
            is_duplicate = await self.state_store.is_message_processed(
                inbound.external_user_id,
                inbound.channel.value,
                inbound.external_user_id,
                inbound.provider_message_id,
            )
            if is_duplicate:
                app_logger.info(
                    "Duplicate message skipped",
                    event="duplicate_skipped",
                    message_id=inbound.provider_message_id,
                )
                return ProcessResult()

        tenant = await self.tenant_service.get_vendor_by_slug(inbound.vendor_slug)
        if not tenant:
            app_logger.warn(
                "Tenant not found for inbound message",
                event="tenant_not_found",
                tenant_slug=inbound.vendor_slug,
            )
            return ProcessResult()

        channel_config = self.tenant_service.get_channel_config(tenant, inbound.channel)
        if not channel_config:
            app_logger.warn(
                "Channel not configured for tenant",
                event="channel_not_configured",
                tenant_slug=inbound.vendor_slug,
                channel=inbound.channel.value,
            )
            return ProcessResult()

        state = await self.state_store.get_state(
            str(tenant.id), inbound.channel.value, inbound.external_user_id
        )
        if state is None:
            state = ConversationState(
                vendor_id=str(tenant.id),
                channel=inbound.channel,
                external_user_id=inbound.external_user_id,
            )
        state.updated_at = datetime.now(timezone.utc)
        await self.state_store.save_state(state)

        echo_text = f"received: {inbound.text or ''}"
        await self.dispatcher.send_instruction(
            channel_config=channel_config,
            destination=inbound.external_user_id,
            instruction=OutboundInstruction(text=echo_text),
        )

        if inbound.provider_message_id:
            await self.state_store.mark_message_processed(
                inbound.external_user_id,
                inbound.channel.value,
                inbound.external_user_id,
                inbound.provider_message_id,
            )

        app_logger.info(
            "Echo dispatched",
            event="echo_dispatched",
            tenant_slug=inbound.vendor_slug,
            channel=inbound.channel.value,
            external_user_id=inbound.external_user_id,
        )

        return ProcessResult(
            processed_messages=1,
            outbound_messages=[echo_text],
        )
