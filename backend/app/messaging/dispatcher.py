from __future__ import annotations

import httpx

from app.core.config import Settings
from app.core.enums import ChannelType
from app.db.models.vendor import VendorChannel
from app.messaging.base import DeliveryResult
from app.messaging.telegram import TelegramTransport
from app.messaging.whatsapp import WhatsAppTransport
from app.schemas.messages import OutboundInstruction


class MessageDispatcher:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.telegram = TelegramTransport(settings, http_client)
        self.whatsapp = WhatsAppTransport(settings, http_client)

    async def send_instruction(
        self,
        channel_config: VendorChannel,
        destination: str,
        instruction: OutboundInstruction,
    ) -> list[DeliveryResult]:
        if channel_config.channel == ChannelType.TELEGRAM:
            return await self.telegram.send_instruction(channel_config, destination, instruction)
        if channel_config.channel == ChannelType.WHATSAPP:
            return await self.whatsapp.send_instruction(channel_config, destination, instruction)
        return []
