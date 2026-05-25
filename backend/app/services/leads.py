"""Lead-capture service — the producer half of the transactional outbox.

Every public lead form (inquiry, callback, application, cost estimate, QR scan)
flows through :class:`LeadCaptureService`. The service does ONE thing per
submission and does it atomically:

    1. validate the input,
    2. persist the lead row, AND
    3. persist an ``OutboxEvent`` describing the notification to send,

all in the **same transaction / single commit**. It NEVER performs SMTP or HTTP
itself, and it NEVER commits the lead and then enqueues a job separately — that
dual write is exactly the failure mode the outbox eliminates. If the commit
fails, neither the lead nor its notification exists; if it succeeds, both do, and
the worker is guaranteed to find the job.

Transaction ownership
----------------------
The service does NOT commit. It flushes (to populate the lead id used by the
outbox event's ``aggregate_id``) and leaves the commit to the caller's session
context:

* From FastAPI routes, wrap the call in ``session.begin()`` or commit after — the
  route owns the request-scoped session (``get_session``).
* From workers/scripts, ``session_scope`` commits on clean exit.

Because the lead INSERT, the flush, and the OutboxEvent INSERT all happen on the
same ``AsyncSession`` before any commit, they land in one transaction.

Public API (stable — orchestrator wires these into routes)
-----------------------------------------------------------
``svc = LeadCaptureService(session)`` then await one of:

    await svc.capture_inquiry(vendor_id, data: InquiryIn)      -> LeadAccepted
    await svc.capture_callback(vendor_id, data: CallbackIn)    -> LeadAccepted
    await svc.capture_application(vendor_id, data: ApplicationIn) -> LeadAccepted
    await svc.capture_cost_estimate(vendor_id, data: CostEstimateIn) -> LeadAccepted
    await svc.capture_qr_scan(vendor_id, data: QrScanIn)       -> LeadAccepted

Each returns ``LeadAccepted(id=<lead uuid>, event_type=<str>)``. The caller
commits the session; on commit the worker will deliver the notification.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.observability import get_logger
from app.db.models.leads import (
    Application,
    Callback,
    CostEstimate,
    Inquiry,
    QrLog,
)
from app.db.models.outbox import OutboxEvent

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Input / output value objects (framework-agnostic — routes adapt Pydantic to
# these so the service has no FastAPI dependency).
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class InquiryIn:
    name: str
    email: str
    message: str
    ip: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass(slots=True)
class CallbackIn:
    name: str
    phone: str
    email: Optional[str] = None
    preferred_time: Optional[str] = None
    ip: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass(slots=True)
class ApplicationIn:
    name: str
    email: str
    phone: str
    education: Optional[str] = None
    course: Optional[str] = None
    country: Optional[str] = None
    intake: Optional[str] = None
    message: Optional[str] = None
    ip: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass(slots=True)
class CostEstimateIn:
    name: str
    email: str
    phone: str
    country: str
    duration_months: int
    study_level: Optional[str] = None
    course: Optional[str] = None
    intake: Optional[str] = None
    currency: Optional[str] = None
    est_tuition: Optional[float] = None
    est_stay: Optional[float] = None
    est_food: Optional[float] = None
    est_total: Optional[float] = None
    ip: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass(slots=True)
class QrScanIn:
    url: str
    ip: Optional[str] = None


@dataclass(slots=True)
class LeadAccepted:
    """Result of a capture: the new lead id and the queued event type."""

    id: UUID
    event_type: str


class LeadValidationError(ValueError):
    """Raised when submitted lead data fails service-level validation."""


def _require(value: Optional[str], field: str) -> str:
    v = (value or "").strip()
    if not v:
        raise LeadValidationError(f"{field} is required")
    return v


def _looks_like_email(value: str) -> bool:
    return "@" in value and "." in value.split("@")[-1]


def _esc(value: Optional[str]) -> str:
    return html.escape(value or "")


class LeadCaptureService:
    """Persist a lead + its notification OutboxEvent in one transaction.

    The service flushes but never commits; the caller owns the commit (see
    module docstring). Construct per request with the active ``AsyncSession``.
    """

    def __init__(self, session: AsyncSession, settings: Optional[Settings] = None) -> None:
        self._session = session
        self._settings = settings or get_settings()

    # -- public capture methods --------------------------------------------
    async def capture_inquiry(self, vendor_id: UUID, data: InquiryIn) -> LeadAccepted:
        name = _require(data.name, "name")
        email = _require(data.email, "email")
        if not _looks_like_email(email):
            raise LeadValidationError("email is invalid")
        message = _require(data.message, "message")

        lead = Inquiry(
            vendor_id=vendor_id,
            name=name,
            email=email,
            message=message,
            ip=data.ip,
            user_agent=data.user_agent,
        )
        subject = f"New inquiry from {name}"
        body = (
            f"<p><strong>Name:</strong> {_esc(name)}</p>"
            f"<p><strong>Email:</strong> {_esc(email)}</p>"
            f"<p><strong>Message:</strong> {_esc(message)}</p>"
        )
        return await self._persist(
            lead=lead,
            vendor_id=vendor_id,
            event_type="lead.inquiry",
            aggregate_type="inquiry",
            subject=subject,
            html_body=body,
            reply_to=email,
        )

    async def capture_callback(self, vendor_id: UUID, data: CallbackIn) -> LeadAccepted:
        name = _require(data.name, "name")
        phone = _require(data.phone, "phone")
        email = (data.email or "").strip() or None
        if email and not _looks_like_email(email):
            raise LeadValidationError("email is invalid")

        lead = Callback(
            vendor_id=vendor_id,
            name=name,
            phone=phone,
            email=email,
            preferred_time=data.preferred_time,
            ip=data.ip,
            user_agent=data.user_agent,
        )
        body = (
            f"<p><strong>Name:</strong> {_esc(name)}</p>"
            f"<p><strong>Phone:</strong> {_esc(phone)}</p>"
            f"<p><strong>Email:</strong> {_esc(email)}</p>"
            f"<p><strong>Preferred time:</strong> {_esc(data.preferred_time)}</p>"
        )
        return await self._persist(
            lead=lead,
            vendor_id=vendor_id,
            event_type="lead.callback",
            aggregate_type="callback",
            subject=f"Callback request from {name}",
            html_body=body,
            reply_to=email,
        )

    async def capture_application(
        self, vendor_id: UUID, data: ApplicationIn
    ) -> LeadAccepted:
        name = _require(data.name, "name")
        email = _require(data.email, "email")
        if not _looks_like_email(email):
            raise LeadValidationError("email is invalid")
        phone = _require(data.phone, "phone")

        lead = Application(
            vendor_id=vendor_id,
            name=name,
            email=email,
            phone=phone,
            education=data.education,
            course=data.course,
            country=data.country,
            intake=data.intake,
            message=data.message,
            ip=data.ip,
            user_agent=data.user_agent,
        )
        body = (
            f"<p><strong>Name:</strong> {_esc(name)}</p>"
            f"<p><strong>Email:</strong> {_esc(email)}</p>"
            f"<p><strong>Phone:</strong> {_esc(phone)}</p>"
            f"<p><strong>Course:</strong> {_esc(data.course)}</p>"
            f"<p><strong>Country:</strong> {_esc(data.country)}</p>"
            f"<p><strong>Intake:</strong> {_esc(data.intake)}</p>"
            f"<p><strong>Education:</strong> {_esc(data.education)}</p>"
            f"<p><strong>Message:</strong> {_esc(data.message)}</p>"
        )
        return await self._persist(
            lead=lead,
            vendor_id=vendor_id,
            event_type="lead.application",
            aggregate_type="application",
            subject=f"New application from {name}",
            html_body=body,
            reply_to=email,
        )

    async def capture_cost_estimate(
        self, vendor_id: UUID, data: CostEstimateIn
    ) -> LeadAccepted:
        name = _require(data.name, "name")
        email = _require(data.email, "email")
        if not _looks_like_email(email):
            raise LeadValidationError("email is invalid")
        phone = _require(data.phone, "phone")
        country = _require(data.country, "country")
        if data.duration_months is None or data.duration_months <= 0:
            raise LeadValidationError("duration_months must be a positive integer")

        lead = CostEstimate(
            vendor_id=vendor_id,
            name=name,
            email=email,
            phone=phone,
            country=country,
            study_level=data.study_level,
            course=data.course,
            intake=data.intake,
            duration_months=data.duration_months,
            currency=data.currency,
            est_tuition=data.est_tuition,
            est_stay=data.est_stay,
            est_food=data.est_food,
            est_total=data.est_total,
            ip=data.ip,
            user_agent=data.user_agent,
        )
        body = (
            f"<p><strong>Name:</strong> {_esc(name)}</p>"
            f"<p><strong>Email:</strong> {_esc(email)}</p>"
            f"<p><strong>Phone:</strong> {_esc(phone)}</p>"
            f"<p><strong>Country:</strong> {_esc(country)}</p>"
            f"<p><strong>Course:</strong> {_esc(data.course)}</p>"
            f"<p><strong>Estimated total:</strong> {_esc(data.currency)} "
            f"{data.est_total if data.est_total is not None else ''}</p>"
        )
        return await self._persist(
            lead=lead,
            vendor_id=vendor_id,
            event_type="lead.cost_estimate",
            aggregate_type="cost_estimate",
            subject=f"New cost-estimate lead from {name}",
            html_body=body,
            reply_to=email,
        )

    async def capture_qr_scan(self, vendor_id: Optional[UUID], data: QrScanIn) -> LeadAccepted:
        url = _require(data.url, "url")
        lead = QrLog(vendor_id=vendor_id, url=url, ip=data.ip)
        body = f"<p><strong>QR scan:</strong> {_esc(url)}</p>"
        return await self._persist(
            lead=lead,
            vendor_id=vendor_id,
            event_type="lead.qr_scan",
            aggregate_type="qr_log",
            subject="QR code scanned",
            html_body=body,
            reply_to=None,
        )

    # -- single-transaction persistence ------------------------------------
    async def _persist(
        self,
        *,
        lead: object,
        vendor_id: Optional[UUID],
        event_type: str,
        aggregate_type: str,
        subject: str,
        html_body: str,
        reply_to: Optional[str],
    ) -> LeadAccepted:
        """Write the lead + its OutboxEvent atomically on one session.

        Flushes once to obtain the lead's server-side id (used as the outbox
        ``aggregate_id`` and to build a stable ``dedup_key``). NO commit here —
        the caller's transaction scope commits both rows together.
        """
        session = self._session

        session.add(lead)
        await session.flush()  # populate lead.id within the same transaction
        lead_id: UUID = lead.id  # type: ignore[attr-defined]

        notify_to = self._settings.business_email or self._settings.email_from
        payload: dict[str, object] = {
            "to_email": notify_to,
            "subject": subject,
            "html_body": html_body,
            "lead_id": str(lead_id),
            "vendor_id": str(vendor_id) if vendor_id else None,
            "event_type": event_type,
        }
        if reply_to:
            payload["reply_to"] = reply_to

        # dedup_key uniquely identifies the notification intent so an
        # accidental re-enqueue (or worker replay) collapses to one delivery.
        dedup_key = f"{event_type}:{lead_id}"

        event = OutboxEvent(
            id=uuid4(),
            vendor_id=vendor_id,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=lead_id,
            payload=payload,
            dedup_key=dedup_key,
        )
        session.add(event)
        await session.flush()  # surface any constraint error to the caller now

        logger.info(
            "lead_captured",
            event_type=event_type,
            lead_id=str(lead_id),
            vendor_id=str(vendor_id) if vendor_id else None,
            outbox_event_id=str(event.id),
        )
        return LeadAccepted(id=lead_id, event_type=event_type)
