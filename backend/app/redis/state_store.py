from __future__ import annotations

from redis.asyncio import Redis

from app.schemas.state import ConversationState
from app.utils.logger import app_logger


class RedisStateStore:
    def __init__(self, redis_client: Redis, ttl_seconds: int) -> None:
        self.redis_client = redis_client
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _key(vendor_id: str, channel: str, external_user_id: str) -> str:
        return f"conv:{vendor_id}:{channel}:{external_user_id}"

    async def get_state(
        self,
        vendor_id: str,
        channel: str,
        external_user_id: str,
    ) -> ConversationState | None:
        try:
            raw_state = await self.redis_client.get(self._key(vendor_id, channel, external_user_id))
        except Exception as e:
            app_logger.error(
                "Redis GET failed",
                event="redis_error",
                operation="GET",
                key=self._key(vendor_id, channel, external_user_id),
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise
        if not raw_state:
            return None
        return ConversationState.model_validate_json(raw_state)

    async def save_state(self, state: ConversationState) -> None:
        key = self._key(state.vendor_id, state.channel.value, state.external_user_id)
        try:
            await self.redis_client.set(key, state.model_dump_json(), ex=self.ttl_seconds)
        except Exception as e:
            app_logger.error(
                "Redis SET failed",
                event="redis_error",
                operation="SET",
                key=key,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    async def clear_state(self, vendor_id: str, channel: str, external_user_id: str) -> None:
        key = self._key(vendor_id, channel, external_user_id)
        try:
            await self.redis_client.delete(key)
        except Exception as e:
            app_logger.error(
                "Redis DELETE failed",
                event="redis_error",
                operation="DELETE",
                key=key,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    async def is_message_processed(self, vendor_id: str, channel: str, external_user_id: str, message_id: str) -> bool:
        """Check if a message has already been processed (deduplication)."""
        if not message_id:
            return False
        key = f"msg:{vendor_id}:{channel}:{external_user_id}:{message_id}"
        try:
            exists = await self.redis_client.exists(key)
            return bool(exists)
        except Exception:
            return False

    async def mark_message_processed(self, vendor_id: str, channel: str, external_user_id: str, message_id: str) -> None:
        """Mark a message as processed to prevent duplicate processing."""
        if not message_id:
            return
        key = f"msg:{vendor_id}:{channel}:{external_user_id}:{message_id}"
        try:
            # Store for 1 hour (enough for webhook retries)
            await self.redis_client.set(key, "1", ex=3600)
        except Exception as e:
            app_logger.error(
                "Failed to mark message processed",
                event="redis_error",
                operation="SET",
                key=key,
                error_type=type(e).__name__,
                error_message=str(e),
            )
