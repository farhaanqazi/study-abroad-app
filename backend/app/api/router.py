from __future__ import annotations

from fastapi import APIRouter

from app.api import leads, me, vendor_console

api_router = APIRouter()
# Public, per-vendor lead capture (/v/{vendor_slug}/...).
api_router.include_router(leads.router)
# Authenticated identity (/me) — current user + their vendor memberships.
api_router.include_router(me.router)
# Authenticated, tenant-scoped management console (/console/{vendor_id}/...).
api_router.include_router(vendor_console.router)
