from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.core.enums import ChannelType
from app.schemas.state import ConversationState


class NormalizedInboundMessage(BaseModel):
    vendor_slug: str
    channel: ChannelType
    external_user_id: str
    text: str
    raw_payload: dict[str, Any]
    provider_message_id: str | None = None
    display_name: str | None = None
    phone_number: str | None = None
    telegram_chat_id: str | None = None


class OutboundInstruction(BaseModel):
    text: str
    media_urls: list[str] = Field(default_factory=list)
    # Inline keyboard buttons for Telegram (list of label/callback pairs)
    buttons: list[dict[str, str]] = Field(default_factory=list)  # [{"label": "English", "callback": "lang_english"}]

    @field_validator("buttons", mode="before")
    @classmethod
    def normalize_button_payload(cls, value: Any) -> Any:
        # _build_date_buttons/_build_time_buttons return (buttons, booked_text).
        # If a caller accidentally passes that whole tuple, keep only buttons.
        if (
            isinstance(value, tuple)
            and len(value) == 2
            and isinstance(value[0], list)
            and isinstance(value[1], str)
        ):
            return value[0]
        return value


class FlowResult(BaseModel):
    state: ConversationState
    messages: list[OutboundInstruction] = Field(default_factory=list)
    clear_state: bool = False
    should_create_appointment: bool = False
    should_cancel_appointment: bool = False
    should_update_appointment: bool = False


class ProcessResult(BaseModel):
    processed_messages: int = 0
    outbound_messages: list[str] = Field(default_factory=list)
    created_booking_reference: str | None = None
