"""Admin: back-office support tickets.

List/create/detail/add-message require SUPPORT+; status/assignee mutations
require ADMIN+ and are audited. Routes validate → authorize → delegate →
serialize; logic lives in :mod:`app.services.support`.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.dependencies.auth import PlatformContext, PlatformRequire
from app.core.enums import PlatformRole, SupportTicketStatus
from app.db.models.support import SupportTicket
from app.schemas.support import (
    SupportTicketCreate,
    SupportTicketDetailOut,
    SupportTicketMessageCreate,
    SupportTicketMessageOut,
    SupportTicketOut,
    SupportTicketUpdate,
)
from app.services import support as svc

router = APIRouter(prefix="/support/tickets", tags=["admin: support"])

require_support = PlatformRequire(PlatformRole.SUPPORT)
require_admin = PlatformRequire(PlatformRole.ADMIN)


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _ticket_out(ticket: SupportTicket) -> SupportTicketOut:
    return SupportTicketOut(
        id=str(ticket.id),
        vendor_id=str(ticket.vendor_id) if ticket.vendor_id else None,
        opened_by_user_id=str(ticket.opened_by_user_id) if ticket.opened_by_user_id else None,
        assignee_user_id=str(ticket.assignee_user_id) if ticket.assignee_user_id else None,
        subject=ticket.subject,
        status=ticket.status.value,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


def _detail_out(ticket: SupportTicket) -> SupportTicketDetailOut:
    return SupportTicketDetailOut(
        **_ticket_out(ticket).model_dump(),
        messages=[
            SupportTicketMessageOut(
                id=str(m.id),
                ticket_id=str(m.ticket_id),
                author_user_id=str(m.author_user_id) if m.author_user_id else None,
                body=m.body,
                is_internal=m.is_internal,
                created_at=m.created_at,
            )
            for m in ticket.messages
        ],
    )


@router.get("", response_model=list[SupportTicketOut])
async def list_tickets(
    ctx: PlatformContext = Depends(require_support),
    db: AsyncSession = Depends(get_db),
    status: Optional[SupportTicketStatus] = Query(None),
    vendor_id: Optional[UUID] = Query(None),
    assignee_user_id: Optional[UUID] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[SupportTicketOut]:
    tickets = await svc.list_tickets(
        db,
        status=status,
        vendor_id=vendor_id,
        assignee_user_id=assignee_user_id,
        limit=limit,
        offset=offset,
    )
    return [_ticket_out(t) for t in tickets]


@router.post("", response_model=SupportTicketDetailOut, status_code=201)
async def create_ticket(
    payload: SupportTicketCreate,
    request: Request,
    ctx: PlatformContext = Depends(require_support),
    db: AsyncSession = Depends(get_db),
) -> SupportTicketDetailOut:
    vendor_uuid: Optional[UUID] = None
    if payload.vendor_id:
        try:
            vendor_uuid = UUID(payload.vendor_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="vendor_id must be a valid UUID.")
    try:
        ticket = await svc.create_ticket(
            db,
            operator=ctx.user,
            subject=payload.subject,
            body=payload.body,
            vendor_id=vendor_uuid,
            ip=_client_ip(request),
        )
    except svc.SupportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return _detail_out(ticket)


@router.get("/{ticket_id}", response_model=SupportTicketDetailOut)
async def get_ticket(
    ticket_id: UUID,
    ctx: PlatformContext = Depends(require_support),
    db: AsyncSession = Depends(get_db),
) -> SupportTicketDetailOut:
    try:
        ticket = await svc.get_ticket(db, ticket_id=ticket_id)
    except svc.SupportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return _detail_out(ticket)


@router.post("/{ticket_id}/messages", response_model=SupportTicketDetailOut, status_code=201)
async def add_message(
    ticket_id: UUID,
    payload: SupportTicketMessageCreate,
    request: Request,
    ctx: PlatformContext = Depends(require_support),
    db: AsyncSession = Depends(get_db),
) -> SupportTicketDetailOut:
    try:
        ticket = await svc.add_message(
            db,
            operator=ctx.user,
            ticket_id=ticket_id,
            body=payload.body,
            is_internal=payload.is_internal,
            ip=_client_ip(request),
        )
    except svc.SupportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return _detail_out(ticket)


@router.patch("/{ticket_id}", response_model=SupportTicketDetailOut)
async def update_ticket(
    ticket_id: UUID,
    payload: SupportTicketUpdate,
    request: Request,
    ctx: PlatformContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SupportTicketDetailOut:
    assignee_uuid: Optional[UUID] = None
    if payload.assignee_user_id:
        try:
            assignee_uuid = UUID(payload.assignee_user_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="assignee_user_id must be a valid UUID.")
    try:
        ticket = await svc.update_ticket(
            db,
            admin=ctx.user,
            ticket_id=ticket_id,
            status=payload.status,
            assignee_user_id=assignee_uuid,
            ip=_client_ip(request),
        )
    except svc.SupportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return _detail_out(ticket)
