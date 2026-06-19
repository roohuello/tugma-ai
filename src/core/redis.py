from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langgraph.store.redis import RedisStore

from src.config import settings


def get_checkpointer() -> AsyncRedisSaver:
    return AsyncRedisSaver(
        redis_url=settings.redis_url,
        ttl=settings.session_ttl_minutes * 60,
    )


def get_store() -> RedisStore:
    return RedisStore(
        redis_url=settings.redis_url,
        ttl=settings.session_ttl_minutes * 60,
    )
