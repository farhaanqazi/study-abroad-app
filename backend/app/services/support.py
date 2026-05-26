"""Back-office support-ticket services.

List/create/detail are operator (support+) actions; status/assignee mutations
are admin+ and audited. Like the rest of the ops layer, business logic lives
here and failures raise :class:`SupportError` with an HTTP status hint.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SupportTicketStatus
from app.db.models.support import SupportTicket, SupportTicketMessage
from app.db.models.tenant import User, Vendor
from app.services import audit


class SupportError(Exception):
    """Domain error with an HTTP-friendly status hint."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _parse_status(raw: str) -> SupportTicketStatus:
    try:
        return SupportTicketStatus(raw)
    except ValueError as exc:
        valid = ", ".join(s.value for s in SupportTicketStatus)
        raise SupportError(f"Invalid status; expected one of: {valid}.", 422) from exc


async def list_tickets(
    session: AsyncSession,
    *,
    status: Optional[SupportTicketStatus] = None,
    vendor_id: Optional[UUID] = None,
    assignee_user_id: Optional[UUID] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[SupportTicket]:
    stmt = select(SupportTicket).order_by(SupportTicket.created_at.desc())
    if status is not None:
        stmt = stmt.where(SupportTicket.status == status)
    if vendor_id is not None:
        stmt = stmt.where(SupportTicket.vendor_id == vendor_id)
    if assignee_user_id is not None:
        stmt = stmt.where(SupportTicket.assignee_user_id == assignee_user_id)
    stmt = stmt.limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)


async def get_ticket(session: AsyncSession, *, ticket_id: UUID) -> SupportTicket:
    stmt = (
        select(SupportTicket)
        .where(SupportTicket.id == ticket_id)
        .options(selectinload(SupportTicket.messages))
    )
    ticket = await session.scalar(stmt)
    if ticket is None:
        raise SupportError("Support ticket not found.", 404)
    return ticket


async def create_ticket(
    session: AsyncSession,
    *,
    operator: User,
    subject: str,
    body: str,
    vendor_id: Optional[UUID] = None,
    ip: Optional[str] = None,
) -> SupportTicket:
    """Create a ticket + its first message in one transaction. Audited."""
    if not subject.strip():
        raise SupportError("Subject is required.", 422)
    if not body.strip():
        raise SupportError("Body is required.", 422)

    if vendor_id is not None:
        vendor = await session.get(Vendor, vendor_id)
        if vendor is None:
            raise SupportError("Vendor not found.", 404)

    ticket = SupportTicket(
        vendor_id=vendor_id,
        opened_by_user_id=operator.id,
        subject=subject.strip(),
        status=SupportTicketStatus.OPEN,
    )
    session.add(ticket)
    await session.flush()  # assign ticket.id

    session.add(
        SupportTicketMessage(
            ticket_id=ticket.id,
            author_user_id=operator.id,
            body=body.strip(),
            is_internal=False,
        )
    )

    await audit.record(
        session,
        actor=operator,
        action="support.ticket.create",
        target_type="support_ticket",
        target_id=ticket.id,
        vendor_id=vendor_id,
        details={"subject": ticket.subject},
        ip=ip,
    )
    await session.commit()
    return await get_ticket(session, ticket_id=ticket.id)


async def add_message(
    session: AsyncSession,
    *,
    operator: User,
    ticket_id: UUID,
    body: str,
    is_internal: bool,
    ip: Optional[str] = None,
) -> SupportTicket:
    if not body.strip():
        raise SupportError("Message body is required.", 422)

    ticket = await session.get(SupportTicket, ticket_id)
    if ticket is None:
        raise SupportError("Support ticket not found.", 404)

    session.add(
        SupportTicketMessage(
            ticket_id=ticket.id,
            author_user_id=operator.id,
            body=body.strip(),
            is_internal=is_internal,
        )
    )

    await audit.record(
        session,
        actor=operator,
        action="support.ticket.message",
        target_type="support_ticket",
        target_id=ticket.id,
        vendor_id=ticket.vendor_id,
        details={"is_internal": is_internal},
        ip=ip,
    )
    await session.commit()
    return await get_ticket(session, ticket_id=ticket.id)


async def update_ticket(
    session: AsyncSession,
    *,
    admin: User,
    ticket_id: UUID,
    status: Optional[str] = None,
    assignee_user_id: Optional[UUID] = None,
    ip: Optional[str] = None,
) -> SupportTicket:
    """Admin mutation: set status and/or assignee. At least one field required.
    Audited in the same transaction."""
    if status is None and assignee_user_id is None:
        raise SupportError("Provide at least one of status, assignee_user_id.", 422)

    ticket = await session.get(SupportTicket, ticket_id)
    if ticket is None:
        raise SupportError("Support ticket not found.", 404)

    changes: dict[str, object] = {}
    if status is not None:
        new_status = _parse_status(status)
        changes["status"] = {"from": ticket.status.value, "to": new_status.value}
        ticket.status = new_status
    if assignee_user_id is not None:
        assignee = await session.get(User, assignee_user_id)
        if assignee is None:
            raise SupportError("Assignee user not found.", 404)
        changes["assignee_user_id"] = {
            "from": str(ticket.assignee_user_id) if ticket.assignee_user_id else None,
            "to": str(assignee_user_id),
        }
        ticket.assignee_user_id = assignee_user_id

    await audit.record(
        session,
        actor=admin,
        action="support.ticket.update",
        target_type="support_ticket",
        target_id=ticket.id,
        vendor_id=ticket.vendor_id,
        details={"changes": changes},
        ip=ip,
    )
    await session.commit()
    return await get_ticket(session, ticket_id=ticket.id)
