"""Pydantic Create/Out schemas for the back-office support-ticket API."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SupportTicketCreate(BaseModel):
    subject: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1, max_length=20000)
    vendor_id: Optional[str] = Field(
        None, description="Optionally scope the ticket to a vendor."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "subject": "Vendor cannot publish site config",
                "body": "Owner reports a 500 when publishing. Investigating.",
                "vendor_id": None,
            }
        }
    }


class SupportTicketMessageCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=20000)
    is_internal: bool = Field(
        False, description="Operator-only note, not shown to the vendor."
    )


class SupportTicketUpdate(BaseModel):
    """Admin-only mutation. Both fields optional; at least one must be set."""

    status: Optional[str] = Field(
        None, description="open | pending | resolved | closed"
    )
    assignee_user_id: Optional[str] = Field(None)


class SupportTicketMessageOut(BaseModel):
    id: str
    ticket_id: str
    author_user_id: Optional[str]
    body: str
    is_internal: bool
    created_at: datetime


class SupportTicketOut(BaseModel):
    id: str
    vendor_id: Optional[str]
    opened_by_user_id: Optional[str]
    assignee_user_id: Optional[str]
    subject: str
    status: str
    created_at: datetime
    updated_at: datetime


class SupportTicketDetailOut(SupportTicketOut):
    messages: list[SupportTicketMessageOut]
