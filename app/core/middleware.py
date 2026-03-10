import logging
import time
import uuid

from fastapi import Request

from app.core.logging import request_id_var

logger = logging.getLogger("app.middleware")

async def logging_middleware(request: Request, call_next):
    """
    들어오는 HTTP 요청에 대해 고유한 Request ID를 생성하여 컨텍스트에 저장하고,
    요청 처리 소요 시간과 상태 코드를 포함한 Access 로그를 남깁니다.
    """
    req_id = str(uuid.uuid4())[:8]
    token = request_id_var.set(req_id)
    start_time = time.perf_counter()

    try:
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        client_host = request.client.host if request.client else "unknown"
        client_port = request.client.port if request.client else 0
        
        logger.info(
            f'{client_host}:{client_port} - "{request.method} {request.url.path}" {response.status_code} ({duration_ms:.2f}ms)'
        )
        response.headers["X-Request-ID"] = req_id
        return response
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        client_host = request.client.host if request.client else "unknown"
        client_port = request.client.port if request.client else 0
        
        logger.error(
            f'{client_host}:{client_port} - "{request.method} {request.url.path}" 500 ({duration_ms:.2f}ms) - {e}'
        )
        raise e
    finally:
        request_id_var.reset(token)
