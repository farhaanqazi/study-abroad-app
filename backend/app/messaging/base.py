from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.db.models.vendor import VendorChannel
from app.schemas.messages import OutboundInstruction


@dataclass
class DeliveryResult:
    provider_message_id: str | None
    text: str
    payload: dict[str, Any]


class MessagingTransport(ABC):
    @abstractmethod
    async def send_instruction(
        self,
        channel_config: VendorChannel,
        destination: str,
        instruction: OutboundInstruction,
    ) -> list[DeliveryResult]:
        raise NotImplementedError
