import logging
from typing import Optional
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

class RedisClient:
    _instance: Optional[Redis] = None

    @classmethod
    async def get_instance(cls) -> Redis:
        if cls._instance is None:
            logger.info("Initializing Redis connection pool...")
            cls._instance = Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=2.0
            )

            try:
                await cls._instance.ping()
                logger.info("Redis connection successfully established.")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")

        return cls._instance

    @classmethod
    async def close(cls):
        if cls._instance:
            await cls._instance.aclose()
            logger.info("Redis connection pool closed.")
            cls._instance = None

async def get_redis() -> Redis:
    return await RedisClient.get_instance()
