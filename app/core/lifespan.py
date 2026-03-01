from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool

from app.core.database import check_db_connection, close_db_connection
from app.core.redis import check_redis_connection, close_redis_connection

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """서버 시작 시 DB와 Redis를 워밍업하고, 서버 종료 시 자원을 반환합니다."""
    await run_in_threadpool(check_db_connection)
    await check_redis_connection()

    yield

    await close_redis_connection()
    await run_in_threadpool(close_db_connection)
