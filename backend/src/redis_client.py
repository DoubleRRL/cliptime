"""Shared async Redis client (connection-pooled, lazily initialized)."""

from typing import Optional

import redis.asyncio as redis

from .config import get_config

_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    """Return the shared pooled Redis client, creating it on first use."""
    global _client
    if _client is None:
        config = get_config()
        _client = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            password=config.redis_password,
            decode_responses=True,
            max_connections=50,
        )
    return _client


async def close_redis() -> None:
    """Close the shared client (used during application shutdown)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
