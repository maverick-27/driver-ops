"""Exact-match response cache. Every failure is logged and swallowed: the cache never fails a request."""

import hashlib
import json
import logging
from datetime import timedelta
from typing import Any

import redis.asyncio as redis

from src.config import PROMPT_VERSION, RedisSettings

logger = logging.getLogger(__name__)

KEY_PREFIX = "exact_cache:"


def cache_key(**params: Any) -> str:
    """Every parameter that changes the answer goes in, plus the prompt version."""
    key_data = {**params, "prompt_version": PROMPT_VERSION}
    digest = hashlib.sha256(json.dumps(key_data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:32]
    return KEY_PREFIX + digest


class CacheClient:
    def __init__(self, settings: RedisSettings):
        self.ttl = timedelta(hours=settings.ttl_hours)
        self.redis = redis.Redis(
            host=settings.host,
            port=settings.port,
            password=settings.password or None,
            db=settings.db,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
        )

    async def ping(self) -> bool:
        try:
            return bool(await self.redis.ping())
        except Exception as e:
            logger.warning("Redis ping failed: %s", e)
            return False

    async def get(self, key: str) -> dict[str, Any] | None:
        try:
            value = await self.redis.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.warning("Cache read failed: %s", e)
            return None

    async def set(self, key: str, value: dict[str, Any]) -> None:
        try:
            await self.redis.set(key, json.dumps(value, ensure_ascii=False), ex=self.ttl)
        except Exception as e:
            logger.warning("Cache write failed: %s", e)

    async def close(self) -> None:
        try:
            await self.redis.aclose()
        except Exception:
            pass


def flush_cache_sync(settings: RedisSettings) -> int:
    """Drop all cached answers. Called by ingestion after documents are re-indexed."""
    import redis as sync_redis

    client = sync_redis.Redis(host=settings.host, port=settings.port, password=settings.password or None, db=settings.db)
    keys = list(client.scan_iter(match=KEY_PREFIX + "*"))
    return int(client.delete(*keys)) if keys else 0
