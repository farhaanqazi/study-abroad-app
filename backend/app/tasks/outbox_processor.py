"""Transactional-outbox drain loop.

This is the consumer half of the transactional outbox. The producer half lives
in ``app.services.leads`` (and any other service): it writes a business row and
an ``OutboxEvent`` in the SAME transaction, so a committed lead always has a
committed, durable job. This module reads those jobs back out and performs the
real side effect (email / webhook).

Delivery contract
-----------------
* **At-least-once.** A side effect may run more than once (e.g. the worker dies
  after sending but before marking ``SENT``). Side effects must therefore be
  idempotent; see :func:`already_processed`.
* **A failing event never crashes the worker.** Each event is dispatched inside
  its own try/except and its own short transaction. One poisoned row is retried
  with backoff and eventually parked as ``FAILED`` — it cannot stall siblings.

Claiming
--------
Due ``PENDING`` rows (``available_at <= now``) are claimed oldest-first with
``FOR UPDATE SKIP LOCKED`` and flipped to ``PROCESSING`` in a single short
transaction. ``SKIP LOCKED`` lets multiple worker processes drain concurrently
without contending on the same rows or double-dispatching.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Awaitable, Callable, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OutboxStatus
from app.core.observability import correlation_scope, get_logger
from app.db.models.common import utc_now
from app.db.models.outbox import OutboxEvent, ProcessedEvent
from app.db.session import session_scope
from app.tasks.senders import send_email, send_webhook

logger = get_logger(__name__)

# How many due events one drain pass claims. Bounded so a single pass cannot
# monopolise a worker; the next scheduled pass picks up the remainder.
DRAIN_BATCH_SIZE = 50

# Exponential backoff (seconds) keyed by the attempt number just completed.
# attempt 1 -> +60s, 2 -> +300s, 3 -> +900s, 4 -> +3600s. Capped at the last.
_BACKOFF_SCHEDULE_SECONDS = [60, 300, 900, 3600]


def _backoff_seconds(attempts: int) -> int:
    """Backoff delay after ``attempts`` failed tries (1-based)."""
    idx = max(0, min(attempts - 1, len(_BACKOFF_SCHEDULE_SECONDS) - 1))
    return _BACKOFF_SCHEDULE_SECONDS[idx]


# ---------------------------------------------------------------------------
# Idempotency ledger
# ---------------------------------------------------------------------------
async def already_processed(
    session: AsyncSession,
    source: str,
    external_id: str,
    dedup_hash: Optional[str] = None,
) -> bool:
    """Atomically claim ``(source, external_id)`` in the idempotency ledger.

    Returns ``True`` if this pair was **already** recorded (i.e. the caller
    should treat the work as done and perform no side effect), ``False`` if this
    call is the first to claim it (the caller should proceed).

    The race is resolved by the DB, not by a read-then-write: we attempt the
    INSERT and rely on the ``uq_processed_events_source`` unique constraint. A
    duplicate raises ``IntegrityError`` which we translate into ``True``. This is
    safe under concurrent workers — exactly one INSERT wins.

    A SAVEPOINT (``begin_nested``) isolates the possible IntegrityError so it
    does not poison the surrounding transaction.
    """
    try:
        async with session.begin_nested():
            stmt = (
                pg_insert(ProcessedEvent)
                .values(source=source, external_id=external_id, dedup_hash=dedup_hash)
                .on_conflict_do_nothing(
                    constraint="uq_processed_events_source",
                )
                .returning(ProcessedEvent.id)
            )
            result = await session.execute(stmt)
            inserted = result.scalar_one_or_none()
    except IntegrityError:
        # Belt-and-suspenders: on_conflict_do_nothing should prevent this, but a
        # different unique collision still means "already processed".
        return True

    # inserted is None when ON CONFLICT DO NOTHING suppressed the row -> dup.
    return inserted is None


# ---------------------------------------------------------------------------
# Dispatch table: event_type -> async handler(payload) raising on failure
# ---------------------------------------------------------------------------
async def _handle_lead_notification(event: OutboxEvent) -> None:
    """Deliver a lead-capture notification.

    Payload shape (written by LeadCaptureService):
        {
          "to_email": str,            # recipient (business inbox)
          "subject": str,
          "html_body": str,
          "webhook_url": str | None,  # optional secondary delivery
          "webhook_payload": dict | None,
        }
    Either channel may be present; at least the email channel is expected for
    ``lead.*`` events.
    """
    payload: dict[str, Any] = event.payload or {}

    to_email = payload.get("to_email")
    if to_email:
        await send_email(
            to_email=to_email,
            subject=payload.get("subject", "New lead"),
            html_body=payload.get("html_body", ""),
        )

    webhook_url = payload.get("webhook_url")
    if webhook_url:
        await send_webhook(
            url=webhook_url,
            payload=payload.get("webhook_payload") or payload,
        )


# event_type -> handler. The transactional outbox is event-typed so new
# notification kinds register here without touching the drain loop.
EVENT_HANDLERS: dict[str, Callable[[OutboxEvent], Awaitable[None]]] = {
    "lead.inquiry": _handle_lead_notification,
    "lead.callback": _handle_lead_notification,
    "lead.application": _handle_lead_notification,
    "lead.cost_estimate": _handle_lead_notification,
    "lead.qr_scan": _handle_lead_notification,
}


class UnknownEventType(RuntimeError):
    """Raised when an outbox event has no registered handler."""


# ---------------------------------------------------------------------------
# Claim + dispatch
# ---------------------------------------------------------------------------
async def _claim_due_event_ids(session: AsyncSession, limit: int) -> list[UUID]:
    """Claim up to ``limit`` due PENDING events, flipping them to PROCESSING.

    Uses ``FOR UPDATE SKIP LOCKED`` so concurrent workers never fight over or
    double-claim the same rows. Returns the claimed ids; the surrounding
    ``session_scope`` commits the PROCESSING transition.
    """
    now = utc_now()
    stmt = (
        select(OutboxEvent.id)
        .where(
            OutboxEvent.status == OutboxStatus.PENDING,
            OutboxEvent.available_at <= now,
        )
        .order_by(OutboxEvent.available_at.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    ids = list(result.scalars().all())

    if not ids:
        return []

    for event_id in ids:
        event = await session.get(OutboxEvent, event_id)
        if event is not None:
            event.status = OutboxStatus.PROCESSING
    return ids


async def _record_success(session: AsyncSession, event: OutboxEvent) -> None:
    event.status = OutboxStatus.SENT
    event.processed_at = utc_now()
    event.failure_reason = None


async def _record_failure(session: AsyncSession, event: OutboxEvent, error: str) -> None:
    """Apply retry/backoff or park as FAILED once attempts are exhausted."""
    event.attempts += 1
    event.failure_reason = error[:2000]
    if event.attempts < event.max_attempts:
        event.status = OutboxStatus.PENDING
        event.available_at = utc_now() + timedelta(
            seconds=_backoff_seconds(event.attempts)
        )
        logger.warning(
            "outbox_event_retry_scheduled",
            event_id=str(event.id),
            event_type=event.event_type,
            attempts=event.attempts,
            next_available_at=event.available_at.isoformat(),
        )
    else:
        event.status = OutboxStatus.FAILED
        logger.error(
            "outbox_event_failed_terminal",
            event_id=str(event.id),
            event_type=event.event_type,
            attempts=event.attempts,
            error=error,
        )


async def _dispatch_one(event_id: UUID) -> bool:
    """Dispatch a single claimed event in its own transaction.

    Returns ``True`` on successful delivery, ``False`` otherwise. NEVER raises:
    a per-event failure is recorded and swallowed so one bad event cannot crash
    the worker or stall the batch.
    """
    with correlation_scope():
        try:
            async with session_scope() as session:
                event = await session.get(OutboxEvent, event_id)
                if event is None:
                    return False
                if event.status != OutboxStatus.PROCESSING:
                    # Another worker already advanced it; nothing to do.
                    return False

                handler = EVENT_HANDLERS.get(event.event_type)
                if handler is None:
                    raise UnknownEventType(
                        f"No handler registered for event_type={event.event_type!r}"
                    )

                # Idempotency guard: dedup_key uniquely identifies the intended
                # side effect. If we already delivered it, mark SENT without
                # re-running the side effect.
                dedup = event.dedup_key or str(event.id)
                if await already_processed(
                    session, source="outbox", external_id=dedup
                ):
                    logger.info(
                        "outbox_event_idempotent_skip",
                        event_id=str(event.id),
                        event_type=event.event_type,
                    )
                    await _record_success(session, event)
                    return True

                await handler(event)
                await _record_success(session, event)
                logger.info(
                    "outbox_event_sent",
                    event_id=str(event.id),
                    event_type=event.event_type,
                )
                return True
        except Exception as exc:  # noqa: BLE001 — must never escape per event.
            # Record failure in a fresh transaction (the dispatch txn rolled back).
            try:
                async with session_scope() as session:
                    event = await session.get(OutboxEvent, event_id)
                    if event is not None:
                        await _record_failure(session, event, repr(exc))
            except Exception:  # noqa: BLE001
                logger.exception(
                    "outbox_failure_record_error", event_id=str(event_id)
                )
            return False


async def drain_outbox(batch_size: int = DRAIN_BATCH_SIZE) -> dict[str, int]:
    """Drain one batch of due outbox events. Safe to call repeatedly (cron).

    Returns a small summary dict: ``{"claimed", "sent", "failed"}``. This is the
    function ARQ schedules (see ``app.tasks.arq_settings``).
    """
    async with session_scope() as session:
        claimed_ids = await _claim_due_event_ids(session, batch_size)

    if not claimed_ids:
        return {"claimed": 0, "sent": 0, "failed": 0}

    sent = 0
    failed = 0
    for event_id in claimed_ids:
        ok = await _dispatch_one(event_id)
        if ok:
            sent += 1
        else:
            failed += 1

    summary = {"claimed": len(claimed_ids), "sent": sent, "failed": failed}
    logger.info("outbox_drain_complete", **summary)
    return summary
