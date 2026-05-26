from app.db.models.common import Base
from app.db.models.leads import (
    Application,
    Callback,
    CostEstimate,
    Inquiry,
    QrLog,
)
from app.db.models.invitation import Invitation
from app.db.models.outbox import OutboxEvent, ProcessedEvent
from app.db.models.platform import AuditLog, WorkspaceRequest
from app.db.models.support import SupportTicket, SupportTicketMessage
from app.db.models.tenant import (
    User,
    Vendor,
    VendorMembership,
    VendorSiteConfig,
)
from app.db.models.vendor_cost import VendorCostSetting

__all__ = [
    "Base",
    # Tenancy
    "User",
    "Vendor",
    "VendorMembership",
    "VendorSiteConfig",
    # Platform back-office
    "WorkspaceRequest",
    "AuditLog",
    "Invitation",
    "SupportTicket",
    "SupportTicketMessage",
    # Leads (study-abroad domain)
    "Inquiry",
    "Callback",
    "Application",
    "QrLog",
    "CostEstimate",
    "VendorCostSetting",
    # Async / durability
    "OutboxEvent",
    "ProcessedEvent",
]
