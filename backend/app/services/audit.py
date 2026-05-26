"""Append-only audit logging for platform-operator actions.

`record` adds an :class:`AuditLog` row to the *caller's* session without
committing — so the audit entry lands in the same transaction as the action it
records (either both commit or neither does, preserving integrity). The actor's
platform role is snapshotted so later role changes don't rewrite history.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.platform import AuditLog
from app.db.models.tenant import User

logger = structlog.get_logger(__name__)


async def record(
    session: AsyncSession,
    *,
    actor: Optional[User],
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[UUID] = None,
    vendor_id: Optional[UUID] = None,
    details: Optional[dict[str, Any]] = None,
    ip: Optional[str] = None,
) -> AuditLog:
    entry = AuditLog(
        actor_user_id=actor.id if actor else None,
        actor_role=actor.platform_role.value if actor else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        vendor_id=vendor_id,
        details=details or {},
        ip=ip,
    )
    session.add(entry)
    logger.info(
        "audit",
        action=action,
        actor_id=str(actor.id) if actor else None,
        target_type=target_type,
        target_id=str(target_id) if target_id else None,
        vendor_id=str(vendor_id) if vendor_id else None,
    )
    return entry
