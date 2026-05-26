"""Aggregator for the platform back-office API.

Everything under /api/v1/admin/** lives here. Each sub-router is individually
PlatformRequire-gated (no blanket dependency) so view-only roles (support) can
reach read endpoints while mutations require admin/superadmin. Phases C and D
add their sub-routers via ``admin_router.include_router(...)``.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.admin import (
    audit,
    impersonation,
    members,
    ops,
    support,
    users,
    vendors,
    workspace_requests,
)

admin_router = APIRouter(prefix="/admin")

admin_router.include_router(workspace_requests.router)
admin_router.include_router(vendors.router)
admin_router.include_router(members.router)
admin_router.include_router(users.router)
admin_router.include_router(ops.router)
admin_router.include_router(audit.router)
admin_router.include_router(impersonation.router)
admin_router.include_router(support.router)
