import logging
import time
import uuid
from fastapi import Request

from app.core.logging import request_id_var

logger = logging.getLogger("app.middleware")

EXCLUDE_PATHS = {"/health", "/health/ready"}

def get_client_ip(request: Request) -> str:
    if forwarded_for := request.headers.get("x-forwarded-for"):
        return forwarded_for.split(",", 1)[0].strip()
    if real_ip := request.headers.get("x-real-ip"):
        return real_ip.strip()
    return request.client.host if request.client else "unknown"

async def logging_middleware(request: Request, call_next):
    """
    들어오는 HTTP 요청에 대해 고유한 Request ID를 생성하여 컨텍스트에 저장하고,
    요청 처리 소요 시간과 상태 코드를 포함한 Access 로그를 남깁니다.
    (Health check 등 노이즈는 제외하며 프록시 IP 추적을 지원합니다.)
    """
    req_id = str(uuid.uuid4())[:8]
    token = request_id_var.set(req_id)
    start_time = time.perf_counter()
    is_excluded = request.url.path in EXCLUDE_PATHS

    try:
        response = await call_next(request)
        
        if not is_excluded:
            duration_ms = (time.perf_counter() - start_time) * 1000
            client_ip = get_client_ip(request)
            client_port = request.client.port if request.client else 0
            
            logger.info(
                f'{client_ip}:{client_port} - "{request.method} {request.url.path}" {response.status_code} ({duration_ms:.2f}ms)'
            )
            
        response.headers["X-Request-ID"] = req_id
        return response
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        client_ip = get_client_ip(request)
        client_port = request.client.port if request.client else 0
        
        logger.error(
            f'{client_ip}:{client_port} - "{request.method} {request.url.path}" 500 ({duration_ms:.2f}ms) - {e}'
        )
        raise e
    finally:
        request_id_var.reset(token)
