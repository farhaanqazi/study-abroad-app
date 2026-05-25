from __future__ import annotations

from redis.asyncio import Redis


def build_redis_client(redis_url: str) -> Redis:
    return Redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
