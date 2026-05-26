"""Platform back-office ops services: vendor health, outbox retry, overview,
audit-log search, and read-only view-as helpers.

Business logic lives here (never in route handlers). Service-level failures are
raised as :class:`OpsError` carrying an HTTP status hint, which the route layer
maps to ``HTTPException``. Audit rows are added to the caller's session and
committed in the same transaction as the action they record (fail-closed:
either both land or neither does).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OutboxStatus, VendorStatus, WorkspaceRequestStatus
from app.db.models.leads import (
    Application,
    Callback,
    CostEstimate,
    Inquiry,
    QrLog,
)
from app.db.models.outbox import OutboxEvent
from app.db.models.platform import AuditLog, WorkspaceRequest
from app.db.models.tenant import User, Vendor, VendorSiteConfig
from app.services import audit


class OpsError(Exception):
    """Domain error with an HTTP-friendly status hint."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# Lead models keyed by their public "type" name; reused for counts + view-as.
_LEAD_MODELS: dict[str, Any] = {
    "inquiries": Inquiry,
    "callbacks": Callback,
    "applications": Application,
    "cost_estimates": CostEstimate,
    "qr_logs": QrLog,
}

# Map a lead model back to a singular view-as lead_type label.
_LEAD_TYPE_LABEL: dict[Any, str] = {
    Inquiry: "inquiry",
    Callback: "callback",
    Application: "application",
    CostEstimate: "cost_estimate",
    QrLog: "qr_log",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _require_vendor(session: AsyncSession, vendor_id: UUID) -> Vendor:
    vendor = await session.get(Vendor, vendor_id)
    if vendor is None:
        raise OpsError("Vendor not found.", 404)
    return vendor


# ---------------------------------------------------------------------------
# Vendor health
# ---------------------------------------------------------------------------
async def vendor_health(session: AsyncSession, *, vendor_id: UUID) -> dict[str, Any]:
    """Per-vendor operational snapshot: lead counts, most-recent lead, outbox
    status counts, oldest pending outbox age, and vendor lifecycle flags."""
    vendor = await _require_vendor(session, vendor_id)

    lead_counts: dict[str, int] = {}
    most_recent_lead_at: Optional[datetime] = None
    for key, model in _LEAD_MODELS.items():
        count = await session.scalar(
            select(func.count()).select_from(model).where(model.vendor_id == vendor_id)
        )
        lead_counts[key] = int(count or 0)
        latest = await session.scalar(
            select(func.max(model.created_at)).where(model.vendor_id == vendor_id)
        )
        if latest is not None and (most_recent_lead_at is None or latest > most_recent_lead_at):
            most_recent_lead_at = latest

    lead_counts["total"] = sum(lead_counts.values())

    # Outbox counts by status.
    outbox_counts = {s.value: 0 for s in OutboxStatus}
    rows = (
        await session.execute(
            select(OutboxEvent.status, func.count())
            .where(OutboxEvent.vendor_id == vendor_id)
            .group_by(OutboxEvent.status)
        )
    ).all()
    for status_value, count in rows:
        key = status_value.value if isinstance(status_value, OutboxStatus) else str(status_value)
        outbox_counts[key] = int(count or 0)
    outbox_counts["total"] = sum(
        outbox_counts[s.value] for s in OutboxStatus
    )

    oldest_pending_at = await session.scalar(
        select(func.min(OutboxEvent.available_at)).where(
            OutboxEvent.vendor_id == vendor_id,
            OutboxEvent.status == OutboxStatus.PENDING,
        )
    )
    oldest_pending_age_seconds: Optional[float] = None
    if oldest_pending_at is not None:
        if oldest_pending_at.tzinfo is None:
            oldest_pending_at = oldest_pending_at.replace(tzinfo=timezone.utc)
        oldest_pending_age_seconds = (_utc_now() - oldest_pending_at).total_seconds()

    return {
        "vendor_id": str(vendor.id),
        "slug": vendor.slug,
        "business_name": vendor.business_name,
        "status": vendor.status.value,
        "is_active": vendor.is_active,
        "lead_counts": lead_counts,
        "most_recent_lead_at": most_recent_lead_at,
        "outbox_counts": outbox_counts,
        "oldest_pending_outbox_at": oldest_pending_at,
        "oldest_pending_outbox_age_seconds": oldest_pending_age_seconds,
    }


# ---------------------------------------------------------------------------
# Outbox retry
# ---------------------------------------------------------------------------
async def retry_outbox_event(
    session: AsyncSession,
    *,
    admin: User,
    event_id: UUID,
    ip: Optional[str] = None,
) -> OutboxEvent:
    """Reset a failed/stuck outbox event to PENDING so the worker re-drains it.

    Refuses to touch an already-SENT event (409) — re-sending would duplicate a
    delivered side effect. Audited in the same transaction.
    """
    event = await session.get(OutboxEvent, event_id)
    if event is None:
        raise OpsError("Outbox event not found.", 404)
    if event.status == OutboxStatus.SENT:
        raise OpsError("Event already sent; refusing to retry a delivered event.", 409)

    previous_status = event.status.value
    previous_failure = event.failure_reason

    event.status = OutboxStatus.PENDING
    event.available_at = _utc_now()
    event.failure_reason = None
    event.processed_at = None

    await audit.record(
        session,
        actor=admin,
        action="outbox.retry",
        target_type="outbox_event",
        target_id=event.id,
        vendor_id=event.vendor_id,
        details={
            "event_type": event.event_type,
            "previous_status": previous_status,
            "previous_failure_reason": previous_failure,
            "attempts": event.attempts,
        },
        ip=ip,
    )
    await session.commit()
    await session.refresh(event)
    return event


# ---------------------------------------------------------------------------
# Platform overview
# ---------------------------------------------------------------------------
async def platform_overview(session: AsyncSession) -> dict[str, Any]:
    vendor_counts = {s.value: 0 for s in VendorStatus}
    rows = (
        await session.execute(
            select(Vendor.status, func.count()).group_by(Vendor.status)
        )
    ).all()
    for status_value, count in rows:
        key = status_value.value if isinstance(status_value, VendorStatus) else str(status_value)
        vendor_counts[key] = int(count or 0)
    vendor_counts["total"] = sum(vendor_counts[s.value] for s in VendorStatus)

    pending_requests = await session.scalar(
        select(func.count())
        .select_from(WorkspaceRequest)
        .where(WorkspaceRequest.status == WorkspaceRequestStatus.PENDING)
    )

    total_leads = 0
    for model in _LEAD_MODELS.values():
        count = await session.scalar(select(func.count()).select_from(model))
        total_leads += int(count or 0)

    outbox_failed = await session.scalar(
        select(func.count())
        .select_from(OutboxEvent)
        .where(OutboxEvent.status == OutboxStatus.FAILED)
    )

    since = _utc_now() - timedelta(days=7)
    recent_signups = await session.scalar(
        select(func.count()).select_from(User).where(User.created_at >= since)
    )

    return {
        "vendors": vendor_counts,
        "pending_workspace_requests": int(pending_requests or 0),
        "total_leads": total_leads,
        "outbox_failed": int(outbox_failed or 0),
        "recent_signups_7d": int(recent_signups or 0),
    }


# ---------------------------------------------------------------------------
# Audit-log search (READ-ONLY — append-only table, never mutated here)
# ---------------------------------------------------------------------------
async def search_audit_logs(
    session: AsyncSession,
    *,
    actor_user_id: Optional[UUID] = None,
    action_prefix: Optional[str] = None,
    vendor_id: Optional[UUID] = None,
    target_type: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if actor_user_id is not None:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if action_prefix:
        stmt = stmt.where(AuditLog.action.like(f"{action_prefix}%"))
    if vendor_id is not None:
        stmt = stmt.where(AuditLog.vendor_id == vendor_id)
    if target_type:
        stmt = stmt.where(AuditLog.target_type == target_type)
    if date_from is not None:
        stmt = stmt.where(AuditLog.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(AuditLog.created_at <= date_to)
    stmt = stmt.limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)


# ---------------------------------------------------------------------------
# View-as (READ-ONLY impersonation). Every call writes an audit row.
# ---------------------------------------------------------------------------
async def view_as_leads(
    session: AsyncSession,
    *,
    operator: User,
    vendor_id: UUID,
    limit: int = 50,
    ip: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Return recent leads across all types for a vendor, normalized. Writes an
    ``impersonation.view`` audit row before returning the data."""
    await _require_vendor(session, vendor_id)

    collected: list[dict[str, Any]] = []
    for model in _LEAD_MODELS.values():
        label = _LEAD_TYPE_LABEL[model]
        stmt = (
            select(model)
            .where(model.vendor_id == vendor_id)
            .order_by(model.created_at.desc())
            .limit(limit)
        )
        rows = (await session.execute(stmt)).scalars().all()
        for row in rows:
            collected.append(
                {
                    "id": str(row.id),
                    "lead_type": label,
                    "name": getattr(row, "name", None),
                    "email": getattr(row, "email", None),
                    "created_at": row.created_at,
                }
            )

    collected.sort(key=lambda r: r["created_at"], reverse=True)
    collected = collected[:limit]

    await audit.record(
        session,
        actor=operator,
        action="impersonation.view",
        target_type="vendor",
        target_id=vendor_id,
        vendor_id=vendor_id,
        details={"resource": "leads", "returned": len(collected)},
        ip=ip,
    )
    await session.commit()
    return collected


async def view_as_site_config(
    session: AsyncSession,
    *,
    operator: User,
    vendor_id: UUID,
    ip: Optional[str] = None,
) -> VendorSiteConfig:
    """Return the vendor's site config for troubleshooting. Writes an
    ``impersonation.view`` audit row before returning."""
    await _require_vendor(session, vendor_id)
    config = await session.get(VendorSiteConfig, vendor_id)
    if config is None:
        raise OpsError("Vendor has no site config.", 404)

    await audit.record(
        session,
        actor=operator,
        action="impersonation.view",
        target_type="vendor",
        target_id=vendor_id,
        vendor_id=vendor_id,
        details={"resource": "site-config", "version": config.version},
        ip=ip,
    )
    await session.commit()
    return config
