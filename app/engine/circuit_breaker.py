import logging
from functools import wraps
from typing import Callable, List, Optional
from app.core.redis import RedisClient

logger = logging.getLogger(__name__)

def with_circuit_breaker(
    circuit_id: str,
    fallback_kwargs: Optional[dict] = None,
    target_errors: List[str] = ["503", "500", "429"],
    failure_threshold: int = 2,
    recovery_timeout_secs: int = 180,
):
    """
    서킷 브레이커 + 폴백 라우터 통합 데코레이터
    - 지정된 에러 발생 시 Redis에 실패를 기록합니다.
    - Threshold 도달 시 즉시 OPEN(차단) 상태가 되며, 이후 요청은 대기 없이 fallback_kwargs로 재라우팅됩니다.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            redis_client = await RedisClient.get_instance()

            cb_key = f"circuit_breaker:{circuit_id}"
            status_key = f"{cb_key}:status"
            count_key = f"{cb_key}:fail_count"

            # 1. 서킷 상태 확인
            status = await redis_client.get(status_key)
            if status == "OPEN":
                # 서킷이 닫혀있으므로 바로 Fallback 인자로 교체 후 우회 호출
                logger.warning(f"[{circuit_id}] Server is down. Routing to Fallback Model.")
                if fallback_kwargs:
                    kwargs.update(fallback_kwargs)
                return await func(*args, **kwargs)

            # 2. 메인 로직 수행
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # 3. 에러 분석: 객체의 HTTP 상태 코드를 추출하여 매칭
                status_code = getattr(e, 'code', None) or getattr(e, 'status_code', None)
                
                # 오류 코드가 명시적이지 않다면 에러 메시지 텍스트 파싱을 보조 수단으로 사용
                if not status_code:
                    error_msg = str(e)
                    is_target_error = any(str(code) in error_msg for code in target_errors)
                else:
                    is_target_error = str(status_code) in target_errors
                
                if not is_target_error:
                    # 타깃 에러에 해당하지 않으면 그대로 예외 전달
                    raise e
                
                # 타깃 에러 발생 시 실패 카운트 누적
                fail_count = await redis_client.incr(count_key)
                if fail_count == 1:
                    await redis_client.expire(count_key, 600) # 10분 동안 누적 카운트 유지

                logger.warning(f"[{circuit_id}] Target error detected: {e}. Fail count: {fail_count}/{failure_threshold}")

                if fail_count >= failure_threshold:
                    # 임계치 초과 -> OPEN 전환
                    logger.error(f"[{circuit_id}] Threshold reached! Opening Circuit Breaker for {recovery_timeout_secs}s.")
                    await redis_client.set(status_key, "OPEN", ex=recovery_timeout_secs)
                    await redis_client.delete(count_key) # 카운트 리셋
                    
                    # Fallback으로 재시도
                    if fallback_kwargs:
                        logger.info(f"[{circuit_id}] Immediate Fail-Over to Fallback Model.")
                        kwargs.update(fallback_kwargs)
                        return await func(*args, **kwargs)

                # 카운트 미도달 시 기존 대로 예외 처리
                raise e

        return wrapper
    return decorator
