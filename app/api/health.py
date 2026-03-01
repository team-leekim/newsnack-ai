from fastapi import APIRouter, HTTPException, status
from fastapi.concurrency import run_in_threadpool

from app.core.database import check_db_connection
from app.core.redis import check_redis_connection

router = APIRouter(tags=["System"])

@router.get("/health")
async def liveness_check():
    """서버 프로세스 시작 여부를 확인합니다 (Liveness)."""
    return {"status": "UP"}


@router.get("/health/ready")
async def readiness_check():
    """앱이 트래픽을 처리할 준비가 되었는지 외부 의존성(DB, Redis)을 확인합니다 (Readiness)."""
    try:
        await run_in_threadpool(check_db_connection)
        await check_redis_connection()

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="외부 의존성 연결 실패"
        )

    return {"status": "READY"}
