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


class PlatformRole(str, Enum):
    """Platform-operator privilege tier — ORTHOGONAL to tenant membership.

    This is the back-office axis: it is never derived from VendorMembership and
    never grants tenant write access by itself. Ordered least- to most-
    privileged for hierarchy expansion (a higher tier satisfies a lower one).

    none       — ordinary user, no platform access (default)
    support    — read-only back-office: view workspaces, health, audit
    admin      — manage workspaces/members, approve requests, retry jobs
    superadmin — admin + grant/revoke platform roles, hard-irreversible ops
    """

    NONE = "none"
    SUPPORT = "support"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


class WorkspaceRequestStatus(str, Enum):
    """Lifecycle of a user's request to have a workspace (vendor) provisioned."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class VendorStatus(str, Enum):
    """Admin-controlled lifecycle of a workspace (vendor).

    active    — normal operation
    suspended — reversibly disabled (public site + console blocked)
    deleted   — soft-deleted (hidden; recoverable via deleted_at)
    """

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"
