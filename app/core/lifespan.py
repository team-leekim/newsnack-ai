from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.database import init_db, close_db
from app.core.redis import init_redis, close_redis

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """서버 시작 시 DB와 Redis를 워밍업하고, 서버 종료 시 자원을 반환합니다."""
    init_db()
    await init_redis()
    yield
    await close_redis()
    close_db()
