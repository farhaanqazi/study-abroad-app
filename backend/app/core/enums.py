from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    """Tenant membership roles, ordered most- to least-privileged.

    owner  — full tenant administration (members, billing, site config)
    agent  — operational access (leads, day-to-day management)
    viewer — read-only
    """

    OWNER = "owner"
    AGENT = "agent"
    VIEWER = "viewer"


class OutboxStatus(str, Enum):
    """Lifecycle of a transactional-outbox event drained by the worker."""

    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
