from __future__ import annotations

import warnings
from functools import lru_cache
from typing import Optional

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_name: str = Field(default="Chatbot Starter", validation_alias=AliasChoices("APP_NAME"))
    api_prefix: str = Field(default="/api/v1", validation_alias=AliasChoices("API_PREFIX"))
    environment: str = Field(default="development", validation_alias=AliasChoices("ENVIRONMENT"))
    debug: bool = Field(default=False, validation_alias=AliasChoices("APP_DEBUG"))

    # Database — any SQLAlchemy-supported async URL
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/chatbot",
        validation_alias=AliasChoices("DATABASE_URL"),
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias=AliasChoices("REDIS_URL"),
    )

    # Authentication (Clerk / provider-agnostic OIDC)
    # secret is used for Clerk Backend API calls only — NEVER sent to the JWKS endpoint.
    clerk_secret_key: Optional[str] = Field(default=None, validation_alias=AliasChoices("CLERK_SECRET_KEY"))
    clerk_audience: Optional[str] = Field(default=None, validation_alias=AliasChoices("CLERK_AUDIENCE"))
    clerk_issuer: Optional[str] = Field(default=None, validation_alias=AliasChoices("CLERK_ISSUER"))
    # JWKS endpoint is public; defaults to "{issuer}/.well-known/jwks.json" when unset.
    clerk_jwks_url: Optional[str] = Field(default=None, validation_alias=AliasChoices("CLERK_JWKS_URL"))
    clerk_jwks_cache_ttl_seconds: int = Field(
        default=3600,
        ge=60,
        validation_alias=AliasChoices("CLERK_JWKS_CACHE_TTL_SECONDS"),
    )

    # Platform back-office bootstrap. Comma-separated Clerk user ids and/or
    # emails that are auto-granted the `superadmin` platform role on login.
    # This is the ONLY out-of-UI grant path (solves the first-admin chicken-egg);
    # everyone else is promoted in-console by a superadmin. FAIL-CLOSED: empty
    # (the default) means zero auto-admins, never all.
    platform_superadmins: str = Field(
        default="",
        validation_alias=AliasChoices("PLATFORM_SUPERADMINS", "PLATFORM_SUPERADMIN_CLERK_IDS"),
    )

    @property
    def platform_superadmin_set(self) -> set[str]:
        """Normalized allowlist (lowercased) of clerk ids / emails."""
        return {item.strip().lower() for item in self.platform_superadmins.split(",") if item.strip()}

    @property
    def effective_clerk_jwks_url(self) -> Optional[str]:
        if self.clerk_jwks_url:
            return self.clerk_jwks_url
        if self.clerk_issuer:
            return f"{self.clerk_issuer.rstrip('/')}/.well-known/jwks.json"
        return None

    # LLM
    groq_api_key: Optional[str] = Field(default=None, validation_alias=AliasChoices("GROQ_API_KEY"))
    groq_model: str = Field(default="llama-3.3-70b-versatile", validation_alias=AliasChoices("GROQ_MODEL"))
    groq_base_url: str = Field(
        default="https://api.groq.com/openai/v1",
        validation_alias=AliasChoices("GROQ_BASE_URL"),
    )

    # Server
    app_host: str = Field(default="0.0.0.0", validation_alias=AliasChoices("APP_HOST"))
    app_port: int = Field(default=8000, ge=1, le=65535, validation_alias=AliasChoices("APP_PORT"))
    app_workers: int = Field(default=1, ge=1, validation_alias=AliasChoices("APP_WORKERS"))
    redis_ttl_seconds: int = Field(default=86400, ge=1, validation_alias=AliasChoices("REDIS_TTL_SECONDS"))
    session_ttl_seconds: int = Field(default=86400, ge=1, validation_alias=AliasChoices("SESSION_TTL_SECONDS"))

    # Telegram (bot tokens are stored per-tenant in VendorChannel.provider_config)
    telegram_bot_name: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("TELEGRAM_BOT_NAME"),
    )

    # WhatsApp
    whatsapp_access_token: Optional[str] = Field(default=None, validation_alias=AliasChoices("WHATSAPP_ACCESS_TOKEN"))
    whatsapp_phone_number_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("WHATSAPP_PHONE_NUMBER_ID"),
    )
    whatsapp_verify_token: str = Field(
        default="default_verify_token",
        validation_alias=AliasChoices("WHATSAPP_VERIFY_TOKEN"),
    )

    # Webhooks
    webhook_base_url: str = Field(
        default="http://localhost:8000",
        validation_alias=AliasChoices("WEBHOOK_BASE_URL"),
    )
    default_timezone: str = Field(default="Asia/Kolkata", validation_alias=AliasChoices("DEFAULT_TIMEZONE"))

    # CORS
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        validation_alias=AliasChoices("CORS_ORIGINS"),
    )

    # Email (SMTP)
    email_smtp_host: str = Field(default="", validation_alias=AliasChoices("EMAIL_SMTP_HOST"))
    email_smtp_port: int = Field(default=587, validation_alias=AliasChoices("EMAIL_SMTP_PORT"))
    email_smtp_user: str = Field(default="", validation_alias=AliasChoices("EMAIL_SMTP_USER"))
    email_smtp_password: str = Field(default="", validation_alias=AliasChoices("EMAIL_SMTP_PASSWORD"))
    email_from: str = Field(default="", validation_alias=AliasChoices("EMAIL_FROM"))

    # Lead notifications — inbox that receives lead alerts (global fallback;
    # per-vendor routing is a future enhancement).
    business_email: str = Field(default="", validation_alias=AliasChoices("BUSINESS_EMAIL"))

    # Marketing "stats" baselines surfaced by the public /stats endpoint.
    base_students: int = Field(default=1200, validation_alias=AliasChoices("BASE_STUDENTS"))
    base_countries: int = Field(default=6, validation_alias=AliasChoices("BASE_COUNTRIES"))
    base_universities: int = Field(default=40, validation_alias=AliasChoices("BASE_UNIVERSITIES"))
    base_experience: int = Field(default=12, validation_alias=AliasChoices("BASE_EXPERIENCE"))

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v or "YOUR_DATABASE_PASSWORD" in v or "YOUR_" in v:
            warnings.warn(
                "DATABASE_URL contains placeholder values. Update .env with real credentials.",
                UserWarning,
                stacklevel=2,
            )
        return v

    @field_validator("groq_api_key")
    @classmethod
    def validate_groq_key(cls, v: Optional[str]) -> Optional[str]:
        if v and ("your_" in v.lower() or "placeholder" in v.lower()):
            warnings.warn(
                "GROQ_API_KEY appears to be a placeholder. LLM features will be disabled.",
                UserWarning,
                stacklevel=2,
            )
            return None
        return v

    @model_validator(mode="after")
    def fail_fast_on_production_placeholders(self) -> "Settings":
        if self.environment.strip().lower() != "production":
            return self

        offenders: list[str] = []
        if "YOUR_" in self.database_url.upper() or "PLACEHOLDER" in self.database_url.upper():
            offenders.append("DATABASE_URL")

        # Auth must be fully configured in production — unauthenticated management
        # routes are a hard failure (see TenantRequire).
        missing_auth: list[str] = []
        if not self.clerk_issuer:
            missing_auth.append("CLERK_ISSUER")
        if not self.clerk_audience:
            missing_auth.append("CLERK_AUDIENCE")

        problems: list[str] = []
        if offenders:
            problems.append(f"placeholder values still set for: {', '.join(offenders)}")
        if missing_auth:
            problems.append(f"auth not configured (missing: {', '.join(missing_auth)})")

        if problems:
            raise ValueError(
                "ENVIRONMENT=production but " + "; ".join(problems) + ". "
                "Update .env with real values before starting."
            )
        return self

    @property
    def llm_api_key(self) -> Optional[str]:
        return self.groq_api_key

    @property
    def llm_model(self) -> str:
        return self.groq_model

    @property
    def llm_base_url(self) -> Optional[str]:
        return self.groq_base_url

    @property
    def effective_session_ttl_seconds(self) -> int:
        return self.session_ttl_seconds


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
