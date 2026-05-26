from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceRequestCreate(BaseModel):
    business_name: str = Field(..., min_length=1, max_length=255)
    desired_slug: str = Field(..., min_length=3, max_length=100)
    justification: Optional[str] = Field(None, max_length=2000)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "business_name": "Global Pathways Education",
                "desired_slug": "global-pathways",
                "justification": "Independent agency, ~200 students/yr.",
            }
        }
    )


class WorkspaceRequestOut(BaseModel):
    id: str
    business_name: str
    desired_slug: str
    justification: Optional[str]
    status: str
    rejection_reason: Optional[str]
    created_vendor_id: Optional[str]
    created_at: datetime


class AdminWorkspaceRequestOut(WorkspaceRequestOut):
    """Admin view adds requester identity + review metadata."""

    requested_by_user_id: str
    requester_email: Optional[str]
    reviewed_by_user_id: Optional[str]
    reviewed_at: Optional[datetime]


class ApproveWorkspaceRequestIn(BaseModel):
    slug_override: Optional[str] = Field(
        None, min_length=3, max_length=100,
        description="Use this slug instead of the requested one (e.g. on collision).",
    )


class RejectWorkspaceRequestIn(BaseModel):
    reason: Optional[str] = Field(None, max_length=2000)
