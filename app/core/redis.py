import logging
from typing import Optional
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

class RedisClient:
    _instance: Optional[Redis] = None

    @classmethod
    async def get_instance(cls) -> Redis:
        """Redis 연결 인스턴스를 반환합니다."""
        if cls._instance is None:
            logger.info("Initializing Redis connection pool...")
            cls._instance = Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=2.0
            )
        return cls._instance

    @classmethod
    async def close(cls):
        """Redis 연결을 닫습니다."""
        if cls._instance:
            await cls._instance.aclose()
            logger.info("Redis connection pool closed.")
            cls._instance = None


async def get_redis() -> Redis:
    return await RedisClient.get_instance()


async def close_redis_connection():
    """서버 종료 시 Redis 연결을 닫습니다."""
    await RedisClient.close()


async def check_redis_connection():
    """Redis 연결 상태를 확인합니다."""
    try:
        redis = await get_redis()
        await redis.ping()
        logger.info("Redis connection is healthy.")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        raise e
