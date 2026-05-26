"""Single import surface for Alembic and metadata consumers.

Importing this module registers every ORM model on ``Base.metadata`` so that
``alembic`` autogenerate sees the full target schema. It intentionally imports
*only* the data layer — never services, messaging, or the FastAPI app — so the
migration path stays decoupled from application runtime wiring.
"""

from app.db.models import (  # noqa: F401  (re-exported for metadata registration)
    Application,
    AuditLog,
    Base,
    Callback,
    CostEstimate,
    Inquiry,
    OutboxEvent,
    ProcessedEvent,
    QrLog,
    User,
    Vendor,
    VendorCostSetting,
    VendorMembership,
    VendorSiteConfig,
    WorkspaceRequest,
)

__all__ = [
    "Base",
    "User",
    "Vendor",
    "VendorMembership",
    "VendorSiteConfig",
    "WorkspaceRequest",
    "AuditLog",
    "Inquiry",
    "Callback",
    "Application",
    "QrLog",
    "CostEstimate",
    "VendorCostSetting",
    "OutboxEvent",
    "ProcessedEvent",
]
