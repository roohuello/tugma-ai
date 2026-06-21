from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langgraph.store.redis.aio import AsyncRedisStore

from src.config import settings

_TTL = {"default_ttl": settings.session_ttl_minutes, "refresh_on_read": True}


def get_checkpointer() -> AsyncRedisSaver:
    return AsyncRedisSaver(redis_url=settings.redis_url, ttl=_TTL)


def get_store() -> AsyncRedisStore:
    return AsyncRedisStore(redis_url=settings.redis_url, ttl=_TTL)
