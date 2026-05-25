from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import ChannelType
from app.db.models.vendor import Vendor, VendorChannel


class TenantService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_vendor_by_slug(self, slug: str) -> Vendor | None:
        statement = (
            select(Vendor)
            .options(selectinload(Vendor.channels))
            .where(Vendor.slug == slug, Vendor.is_active.is_(True))
        )
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def get_vendor_by_id(self, vendor_id) -> Vendor | None:
        statement = (
            select(Vendor)
            .options(selectinload(Vendor.channels))
            .where(Vendor.id == vendor_id, Vendor.is_active.is_(True))
        )
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    @staticmethod
    def get_channel_config(vendor: Vendor, channel: ChannelType) -> VendorChannel | None:
        for channel_config in vendor.channels:
            if channel_config.channel == channel and channel_config.is_enabled:
                return channel_config
        return None
