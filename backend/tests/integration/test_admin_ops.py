"""Integration checks for the platform back-office ops/audit/view-as/support
services.

pytest is intentionally NOT a dependency in this environment, so this module is
runnable two ways:

    # standalone (no pytest) against a THROWAWAY db:
    cd backend && PYTHONPATH=. \
      DATABASE_URL="postgresql+asyncpg://isafar@localhost:5432/agency_ops_test?sslmode=disable" \
      ENVIRONMENT=development \
      venv/bin/python tests/integration/test_admin_ops.py

    # or, if pytest + pytest-asyncio are later installed, the ``test_*``
    # coroutines below are picked up directly.

Scenarios (all against a LIVE local Postgres at schema head):

  1. outbox retry resets a FAILED event to PENDING (clears failure_reason,
     available_at=now) and refuses to retry an already-SENT event (409);
  2. vendor_health returns lead/outbox counts for a vendor;
  3. support: create ticket (+first message), add message, admin update;
  4. view-as leads + site-config each write an ``impersonation.view`` audit row
     and are read-only.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select

from app.core.enums import OutboxStatus, SupportTicketStatus, VendorStatus
from app.db.models.leads import Inquiry
from app.db.models.outbox import OutboxEvent
from app.db.models.platform import AuditLog
from app.db.models.tenant import User, Vendor, VendorSiteConfig
from app.db.session import session_scope
from app.services import ops, support


async def _make_user() -> User:
    async with session_scope() as session:
        user = User(
            clerk_id=f"clerk-{uuid4().hex[:12]}",
            email=f"op-{uuid4().hex[:8]}@example.com",
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        session.expunge(user)
        return user


async def _make_vendor() -> Vendor:
    async with session_scope() as session:
        vendor = Vendor(
            slug=f"ops-{uuid4().hex[:10]}",
            business_name="Ops Test Agency",
            is_active=True,
            status=VendorStatus.ACTIVE,
        )
        session.add(vendor)
        await session.flush()  # assign vendor.id before FK reference
        session.add(VendorSiteConfig(vendor_id=vendor.id, config={"theme": "x"}, version=1))
        await session.flush()
        await session.refresh(vendor)
        session.expunge(vendor)
        return vendor


# ---------------------------------------------------------------------------
# 1. outbox retry
# ---------------------------------------------------------------------------
async def test_outbox_retry_resets_failed_and_rejects_sent() -> None:
    admin = await _make_user()
    vendor = await _make_vendor()

    async with session_scope() as session:
        failed = OutboxEvent(
            vendor_id=vendor.id,
            event_type="email.test",
            status=OutboxStatus.FAILED,
            attempts=5,
            max_attempts=5,
            available_at=datetime.now(timezone.utc) - timedelta(hours=1),
            failure_reason="boom",
        )
        sent = OutboxEvent(
            vendor_id=vendor.id,
            event_type="email.test",
            status=OutboxStatus.SENT,
            attempts=1,
            available_at=datetime.now(timezone.utc),
        )
        session.add_all([failed, sent])
        await session.flush()
        failed_id, sent_id = failed.id, sent.id

    async with session_scope() as session:
        event = await ops.retry_outbox_event(session, admin=admin, event_id=failed_id, ip="1.2.3.4")
        assert event.status == OutboxStatus.PENDING, event.status
        assert event.failure_reason is None
        assert event.processed_at is None

    # already-sent => 409
    async with session_scope() as session:
        raised = False
        try:
            await ops.retry_outbox_event(session, admin=admin, event_id=sent_id)
        except ops.OpsError as exc:
            raised = exc.status_code == 409
        assert raised, "retrying a SENT event must raise OpsError(409)"

    # audit row written for the retry
    async with session_scope() as session:
        n = await session.scalar(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.action == "outbox.retry",
                AuditLog.target_id == failed_id,
            )
        )
        assert n == 1, f"expected 1 outbox.retry audit row, got {n}"
    print("PASS test_outbox_retry_resets_failed_and_rejects_sent")


# ---------------------------------------------------------------------------
# 2. vendor health
# ---------------------------------------------------------------------------
async def test_vendor_health_counts() -> None:
    vendor = await _make_vendor()
    async with session_scope() as session:
        session.add(Inquiry(vendor_id=vendor.id, name="Ada", email="a@x.com", message="hi"))
        session.add(
            OutboxEvent(
                vendor_id=vendor.id,
                event_type="email.test",
                status=OutboxStatus.PENDING,
                available_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            )
        )

    async with session_scope() as session:
        data = await ops.vendor_health(session, vendor_id=vendor.id)
        assert data["lead_counts"]["inquiries"] == 1, data["lead_counts"]
        assert data["lead_counts"]["total"] >= 1
        assert data["outbox_counts"]["pending"] == 1, data["outbox_counts"]
        assert data["oldest_pending_outbox_age_seconds"] is not None
        assert data["status"] == "active"
    print("PASS test_vendor_health_counts")


# ---------------------------------------------------------------------------
# 3. support tickets
# ---------------------------------------------------------------------------
async def test_support_ticket_lifecycle() -> None:
    operator = await _make_user()
    admin = await _make_user()
    vendor = await _make_vendor()

    async with session_scope() as session:
        ticket = await support.create_ticket(
            session,
            operator=operator,
            subject="Cannot publish",
            body="Owner sees a 500.",
            vendor_id=vendor.id,
            ip="9.9.9.9",
        )
        ticket_id = ticket.id
        assert len(ticket.messages) == 1, ticket.messages
        assert ticket.status == SupportTicketStatus.OPEN

    async with session_scope() as session:
        ticket = await support.add_message(
            session, operator=operator, ticket_id=ticket_id, body="internal note", is_internal=True
        )
        assert len(ticket.messages) == 2
        assert any(m.is_internal for m in ticket.messages)

    async with session_scope() as session:
        ticket = await support.update_ticket(
            session,
            admin=admin,
            ticket_id=ticket_id,
            status="resolved",
            assignee_user_id=admin.id,
        )
        assert ticket.status == SupportTicketStatus.RESOLVED
        assert ticket.assignee_user_id == admin.id

    async with session_scope() as session:
        n = await session.scalar(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.target_id == ticket_id,
                AuditLog.action.like("support.ticket%"),
            )
        )
        assert n == 3, f"expected 3 support audit rows, got {n}"
    print("PASS test_support_ticket_lifecycle")


# ---------------------------------------------------------------------------
# 4. view-as is read-only + audited
# ---------------------------------------------------------------------------
async def test_view_as_writes_audit() -> None:
    operator = await _make_user()
    vendor = await _make_vendor()
    async with session_scope() as session:
        session.add(Inquiry(vendor_id=vendor.id, name="Bob", email="b@x.com", message="hi"))

    async with session_scope() as session:
        leads = await ops.view_as_leads(session, operator=operator, vendor_id=vendor.id, ip="2.2.2.2")
        assert len(leads) >= 1
        assert leads[0]["lead_type"] == "inquiry"

    async with session_scope() as session:
        config = await ops.view_as_site_config(session, operator=operator, vendor_id=vendor.id)
        assert config.version == 1

    async with session_scope() as session:
        n = await session.scalar(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.action == "impersonation.view",
                AuditLog.vendor_id == vendor.id,
            )
        )
        assert n == 2, f"expected 2 impersonation.view audit rows, got {n}"
    print("PASS test_view_as_writes_audit")


async def _run_all() -> None:
    await test_outbox_retry_resets_failed_and_rejects_sent()
    await test_vendor_health_counts()
    await test_support_ticket_lifecycle()
    await test_view_as_writes_audit()
    print("\nALL ADMIN OPS INTEGRATION CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(_run_all())
