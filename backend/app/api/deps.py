from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.llm.service import LLMService
from app.messaging.dispatcher import MessageDispatcher
from app.redis.state_store import RedisStateStore
from app.services.conversation_service import ConversationService
from app.services.email_service import EmailService


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def get_app_settings() -> Settings:
    return get_settings()


def get_state_store(request: Request) -> RedisStateStore:
    return request.app.state.state_store


def get_llm_service(request: Request) -> LLMService:
    return request.app.state.llm_service


def get_dispatcher(request: Request) -> MessageDispatcher:
    return request.app.state.dispatcher


def get_email_service(request: Request) -> EmailService | None:
    return request.app.state.email_service


def get_conversation_service(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> ConversationService:
    return ConversationService(
        db=db,
        settings=settings,
        state_store=get_state_store(request),
        llm_service=get_llm_service(request),
        dispatcher=get_dispatcher(request),
        email_service=get_email_service(request),
    )


__all__ = [
    "get_db",
    "get_app_settings",
    "get_state_store",
    "get_llm_service",
    "get_dispatcher",
    "get_email_service",
    "get_conversation_service",
]
