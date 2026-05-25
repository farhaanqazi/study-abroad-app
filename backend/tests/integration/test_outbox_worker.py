"""Integration checks for the transactional outbox + worker drain.

pytest is intentionally NOT a dependency in this environment, so this module is
written to be runnable two ways:

    # standalone (no pytest):
    cd backend && PYTHONPATH=. \
      DATABASE_URL="postgresql+asyncpg://isafar@localhost:5432/agency_platform_dev?sslmode=disable" \
      ENVIRONMENT=development \
      venv/bin/python tests/integration/test_outbox_worker.py

    # or, if pytest + pytest-asyncio are later installed, the ``test_*``
    # coroutines below are picked up directly.

Each scenario runs against a LIVE local Postgres at schema head. It exercises:

  1. lead + OutboxEvent are committed together in one transaction;
  2. a failing sender reschedules (PENDING, attempts++, future available_at),
     and after max_attempts the event is parked FAILED with a failure_reason;
  3. a duplicate (source, external_id) in the idempotency ledger is a no-op.

These tests monkeypatch the sender dispatch table so no real SMTP/HTTP happens.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from sqlalchemy import select

from app.core.enums import OutboxStatus
from app.db.models.leads import Inquiry
from app.db.models.outbox import OutboxEvent, ProcessedEvent
from app.db.models.tenant import Vendor
from app.db.session import session_scope
from app.services.leads import InquiryIn, LeadCaptureService
from app.tasks import outbox_processor
from app.tasks.outbox_processor import (
    already_processed,
    drain_outbox,
)


async def _make_vendor():
    """Create a tenant and return its id (detached from the session)."""
    async with session_scope() as session:
        vendor = Vendor(slug=f"test-{uuid4().hex[:10]}", business_name="Test Agency")
        session.add(vendor)
        await session.flush()
        return vendor.id


async def _event_for_lead(lead_id):
    """Fetch the OutboxEvent whose aggregate is the given lead id.

    NOTE: ``LeadAccepted.id`` is the LEAD row id, not the OutboxEvent id — the
    event is found via ``aggregate_id``.
    """
    async with session_scope() as session:
        return (
            await session.execute(
                select(OutboxEvent).where(OutboxEvent.aggregate_id == lead_id)
            )
        ).scalar_one()


# ---------------------------------------------------------------------------
# 1. lead + outbox committed in a single transaction
# ---------------------------------------------------------------------------
async def test_lead_and_outbox_single_transaction() -> None:
    vendor_id = await _make_vendor()

    async with session_scope() as session:  # commits on clean exit -> one txn
        svc = LeadCaptureService(session)
        accepted = await svc.capture_inquiry(
            vendor_id,
            InquiryIn(name="Ada", email="ada@example.com", message="hi there"),
        )

    # Both rows must exist after the single commit.
    async with session_scope() as session:
        lead = await session.get(Inquiry, accepted.id)
        ev = (
            await session.execute(
                select(OutboxEvent).where(OutboxEvent.aggregate_id == accepted.id)
            )
        ).scalar_one()

    assert lead is not None, "lead row missing"
    assert ev is not None, "outbox event missing"
    assert ev.event_type == "lead.inquiry"
    assert ev.status == OutboxStatus.PENDING
    assert ev.vendor_id == vendor_id
    assert ev.payload["to_email"] is not None or ev.payload["to_email"] == ""
    print("PASS test_lead_and_outbox_single_transaction "
          f"(lead={accepted.id}, event={ev.id})")


async def test_rollback_leaves_neither_row() -> None:
    """If the transaction rolls back, NEITHER lead nor outbox event persists."""
    vendor_id = await _make_vendor()
    captured_id = None
    try:
        async with session_scope() as session:
            svc = LeadCaptureService(session)
            accepted = await svc.capture_inquiry(
                vendor_id,
                InquiryIn(name="Grace", email="grace@example.com", message="boom"),
            )
            captured_id = accepted.id
            raise RuntimeError("force rollback")
    except RuntimeError:
        pass

    async with session_scope() as session:
        lead = await session.get(Inquiry, captured_id)
        ev = (
            await session.execute(
                select(OutboxEvent).where(OutboxEvent.aggregate_id == captured_id)
            )
        ).scalar_one_or_none()
    assert lead is None, "lead should not persist after rollback"
    assert ev is None, "outbox event should not persist after rollback"
    print("PASS test_rollback_leaves_neither_row")


# ---------------------------------------------------------------------------
# 2. failing sender reschedules with backoff, then FAILED at max_attempts
# ---------------------------------------------------------------------------
async def test_failing_sender_reschedules_then_fails(monkeypatch=None) -> None:
    vendor_id = await _make_vendor()

    async with session_scope() as session:
        svc = LeadCaptureService(session)
        accepted = await svc.capture_inquiry(
            vendor_id,
            InquiryIn(name="Alan", email="alan@example.com", message="will fail"),
        )

    # Force the handler to always raise.
    async def _boom(event):  # noqa: ANN001
        raise RuntimeError("simulated delivery failure")

    event_id = (await _event_for_lead(accepted.id)).id

    original = dict(outbox_processor.EVENT_HANDLERS)
    outbox_processor.EVENT_HANDLERS["lead.inquiry"] = _boom

    try:
        # Drain repeatedly. Each pass: claim due PENDING -> dispatch -> fail ->
        # reschedule. We force the rescheduled row due immediately so the loop
        # can exhaust max_attempts without sleeping out the backoff.
        async def _force_due(eid):
            async with session_scope() as session:
                ev = await session.get(OutboxEvent, eid)
                if ev and ev.status == OutboxStatus.PENDING:
                    from app.db.models.common import utc_now
                    ev.available_at = utc_now()

        for _ in range(10):
            await _force_due(event_id)
            await drain_outbox()
            async with session_scope() as session:
                ev = await session.get(OutboxEvent, event_id)
            if ev.status == OutboxStatus.FAILED:
                break

        async with session_scope() as session:
            ev = await session.get(OutboxEvent, event_id)

        assert ev.status == OutboxStatus.FAILED, f"expected FAILED, got {ev.status}"
        assert ev.attempts == ev.max_attempts, (
            f"attempts {ev.attempts} != max {ev.max_attempts}"
        )
        assert ev.failure_reason and "simulated delivery failure" in ev.failure_reason
        print("PASS test_failing_sender_reschedules_then_fails "
              f"(attempts={ev.attempts}, status={ev.status.value})")
    finally:
        outbox_processor.EVENT_HANDLERS.clear()
        outbox_processor.EVENT_HANDLERS.update(original)


async def test_success_marks_sent() -> None:
    """A succeeding handler marks the event SENT with processed_at set."""
    vendor_id = await _make_vendor()
    async with session_scope() as session:
        svc = LeadCaptureService(session)
        accepted = await svc.capture_inquiry(
            vendor_id,
            InquiryIn(name="Linus", email="linus@example.com", message="ok"),
        )

    async def _ok(event):  # noqa: ANN001
        return None

    original = dict(outbox_processor.EVENT_HANDLERS)
    outbox_processor.EVENT_HANDLERS["lead.inquiry"] = _ok
    try:
        summary = await drain_outbox()
        ev = await _event_for_lead(accepted.id)
        assert ev.status == OutboxStatus.SENT, f"expected SENT, got {ev.status}"
        assert ev.processed_at is not None
        assert summary["sent"] >= 1
        print(f"PASS test_success_marks_sent (summary={summary})")
    finally:
        outbox_processor.EVENT_HANDLERS.clear()
        outbox_processor.EVENT_HANDLERS.update(original)


# ---------------------------------------------------------------------------
# 3. duplicate (source, external_id) is a no-op via the idempotency ledger
# ---------------------------------------------------------------------------
async def test_already_processed_idempotency() -> None:
    ext = f"ext-{uuid4().hex}"
    async with session_scope() as session:
        first = await already_processed(session, source="webhook", external_id=ext)
    async with session_scope() as session:
        second = await already_processed(session, source="webhook", external_id=ext)

    assert first is False, "first claim should be fresh (False)"
    assert second is True, "second claim should detect duplicate (True)"

    async with session_scope() as session:
        rows = (
            await session.execute(
                select(ProcessedEvent).where(
                    ProcessedEvent.source == "webhook",
                    ProcessedEvent.external_id == ext,
                )
            )
        ).scalars().all()
    assert len(rows) == 1, f"expected exactly 1 ledger row, got {len(rows)}"
    print("PASS test_already_processed_idempotency")


async def _run_all() -> None:
    await test_lead_and_outbox_single_transaction()
    await test_rollback_leaves_neither_row()
    await test_success_marks_sent()
    await test_failing_sender_reschedules_then_fails()
    await test_already_processed_idempotency()
    print("\nALL OUTBOX INTEGRATION CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(_run_all())
