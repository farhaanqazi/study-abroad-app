"""Pydantic Out schemas for the platform back-office ops/audit/view-as APIs.

All models are response shapes (``*Out``) plus a couple of request bodies for
auditable mutations. Read-only by default — the audit-log surface never exposes
a create/update/delete body (audit logs are append-only).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Vendor health (GET /vendors/{vendor_id}/health)
# ---------------------------------------------------------------------------
class LeadCountsOut(BaseModel):
    inquiries: int
    callbacks: int
    applications: int
    cost_estimates: int
    qr_logs: int
    total: int


class OutboxCountsOut(BaseModel):
    pending: int
    processing: int
    sent: int
    failed: int
    total: int


class VendorHealthOut(BaseModel):
    vendor_id: str
    slug: str
    business_name: str
    status: str
    is_active: bool
    lead_counts: LeadCountsOut
    most_recent_lead_at: Optional[datetime]
    outbox_counts: OutboxCountsOut
    oldest_pending_outbox_at: Optional[datetime]
    oldest_pending_outbox_age_seconds: Optional[float]


# ---------------------------------------------------------------------------
# Outbox retry (POST /outbox/{event_id}/retry)
# ---------------------------------------------------------------------------
class OutboxEventOut(BaseModel):
    id: str
    vendor_id: Optional[str]
    event_type: str
    status: str
    attempts: int
    max_attempts: int
    available_at: datetime
    processed_at: Optional[datetime]
    failure_reason: Optional[str]


# ---------------------------------------------------------------------------
# Platform overview (GET /overview)
# ---------------------------------------------------------------------------
class VendorStatusCountsOut(BaseModel):
    active: int
    suspended: int
    deleted: int
    total: int


class PlatformOverviewOut(BaseModel):
    vendors: VendorStatusCountsOut
    pending_workspace_requests: int
    total_leads: int
    outbox_failed: int
    recent_signups_7d: int


# ---------------------------------------------------------------------------
# Audit log viewer (GET /audit-logs)
# ---------------------------------------------------------------------------
class AuditLogOut(BaseModel):
    id: str
    actor_user_id: Optional[str]
    actor_role: Optional[str]
    action: str
    target_type: Optional[str]
    target_id: Optional[str]
    vendor_id: Optional[str]
    details: dict[str, Any]
    ip: Optional[str]
    created_at: datetime


# ---------------------------------------------------------------------------
# View-as (read-only impersonation) — GET /vendors/{vendor_id}/view-as/*
# ---------------------------------------------------------------------------
class ViewAsLeadOut(BaseModel):
    """A single lead, normalized across lead types for troubleshooting."""

    id: str
    lead_type: str
    name: Optional[str]
    email: Optional[str]
    created_at: datetime


class ViewAsLeadsOut(BaseModel):
    vendor_id: str
    leads: list[ViewAsLeadOut]


class ViewAsSiteConfigOut(BaseModel):
    vendor_id: str
    version: int
    config: dict[str, Any]
    draft_config: Optional[dict[str, Any]]
    updated_at: datetime
