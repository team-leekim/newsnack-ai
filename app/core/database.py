import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(settings.DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def init_db():
    """서버 부팅 시 DB 연결 상태를 확인합니다."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection successfully established.")
    except Exception as e:
        logger.error(f"Failed to connect to the database: {e}")
        raise e

def close_db():
    """서버 종료 시 DB 커넥션 풀을 반환합니다."""
    engine.dispose()
    logger.info("Database connection pool closed.")
