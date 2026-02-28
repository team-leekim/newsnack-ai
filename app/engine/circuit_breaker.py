import logging
from functools import wraps
from typing import Callable, List, Optional

from app.core.redis import RedisClient

logger = logging.getLogger(__name__)

def with_circuit_breaker(
    circuit_id: str,
    failure_threshold: int = 2,
    failure_window_secs: int = 60,
    recovery_timeout_secs: int = 180,
    target_errors: List[str] = ["503", "500", "429"],
    fallback_kwargs: Optional[dict] = None,
):
    """
    서킷 브레이커 및 폴백 라우팅 통합 데코레이터

    지정된 에러가 발생하면 분산 환경(Redis)에 실패 횟수를 기록합니다. 임계치 도달 시 
    서킷이 OPEN(차단) 상태가 되며, 지정된 시간 동안 원본 호출을 생략하고 
    fallback_kwargs를 적용하여 즉각적인 우회(Failover) 라우팅을 수행합니다.

    Args:
        circuit_id: 서킷 브레이커의 고유 식별자 
        failure_threshold: 서킷을 OPEN 상태로 전환할 누적 실패 횟수 임계값
        failure_window_secs: 실패 횟수를 누적하는 기준 시간(초). 해당 시간 내 발생한 에러만 합산됨
        recovery_timeout_secs: 서킷 OPEN 상태 유지 시간(초). 만료 시 다시 원본 요청을 시도함
        target_errors: 감지 대상으로 삼을 HTTP 형태의 에러 코드 
        fallback_kwargs: 서킷 OPEN 상태에서 원본 함수 인자를 덮어쓸 매개변수 딕셔너리
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
                # 서킷이 열려있으므로 바로 Fallback 인자로 교체 후 우회 호출
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
                    await redis_client.expire(count_key, failure_window_secs)

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
