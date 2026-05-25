from __future__ import annotations

from fastapi import APIRouter

from app.api import leads, vendor_console, webhooks


api_router = APIRouter()
api_router.include_router(webhooks.router)
api_router.include_router(leads.router)
api_router.include_router(vendor_console.router)
