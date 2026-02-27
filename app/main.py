import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Security

from app.api import contents, debug
from app.core.config import settings
from app.core.database import init_db, close_db
from app.core.redis import init_redis, close_redis
from app.core.security import verify_api_key

logging.basicConfig(level=logging.INFO, 
                    format='%(levelname)s: %(asctime)s - %(name)s - %(message)s',
                    datefmt='%H:%M:%S')

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """서버 시작 시 DB와 Redis를 워밍업하고, 서버 종료 시 자원을 반환합니다."""
    init_db()
    await init_redis()
    yield
    await close_redis()
    close_db()


logger = logging.getLogger(__name__)

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
app.include_router(contents.router, dependencies=[Security(verify_api_key)])
app.include_router(debug.router, dependencies=[Security(verify_api_key)])

@app.get("/health")
async def health_check():
    return {"status": "UP"}
