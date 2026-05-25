from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.enums import ChannelType, ConversationStep, UserIntent


class ConversationSlots(BaseModel):
    language: str | None = None
    customer_name: str | None = None
    marriage_type: str | None = None
    service_id: str | None = None
    service_name: str | None = None
    wants_sample_images: bool | None = None
    appointment_date: date | None = None
    appointment_time: time | None = None
    email: str | None = None
    phone_number: str | None = None


class ConversationState(BaseModel):
    session_id: str = Field(default_factory=lambda: uuid4().hex)
    vendor_id: str
    channel: ChannelType
    external_user_id: str
    intent: UserIntent = UserIntent.NEW_BOOKING
    target_appointment_id: str | None = None
    step: ConversationStep = ConversationStep.GREETING
    previous_step: ConversationStep | None = None
    awaiting_greeting: bool = False
    slots: ConversationSlots = Field(default_factory=ConversationSlots)
    attempt_count: int = 0
    is_complete: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)  # For temporary data like appointment lists
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
