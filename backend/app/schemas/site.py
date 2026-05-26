from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

# A vendor's public site is described by this JSON document. It's stored in
# VendorSiteConfig.config (published) / draft_config (unpublished edits) as JSONB,
# and rendered by the public /v/{slug} page. Keep it small and additive — old
# stored docs must still validate as fields are added (hence all defaults).

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class SiteHero(BaseModel):
    headline: str = Field(default="", max_length=200)
    subheadline: str = Field(default="", max_length=600)
    cta_label: str = Field(default="Get started", max_length=60)


class SiteSections(BaseModel):
    show_stats: bool = True
    show_cost_calculator: bool = True
    show_application: bool = True
    show_callback: bool = True


class SiteConfig(BaseModel):
    """The full editable site document. All fields optional/defaulted."""

    hero: SiteHero = Field(default_factory=SiteHero)
    about: str = Field(default="", max_length=4000)
    primary_color: str = Field(default="#171717", max_length=9)
    sections: SiteSections = Field(default_factory=SiteSections)

    @field_validator("primary_color")
    @classmethod
    def _valid_hex(cls, v: str) -> str:
        v = (v or "").strip() or "#171717"
        if not _HEX_RE.match(v):
            raise ValueError("primary_color must be a hex colour like #1a2b3c")
        return v


class SiteConfigState(BaseModel):
    """Console GET response: published + draft + whether a draft is pending."""

    published: SiteConfig
    draft: Optional[SiteConfig] = None
    version: int
    has_unpublished_changes: bool
