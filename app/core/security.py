import secrets
from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from starlette import status
from app.core.config import settings

API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def verify_api_key(header_value: str = Security(api_key_header)):
    """
    API 키를 검증하는 함수
    
    Args:
        header_value: X-API-KEY 헤더 값
        
    Returns:
        str: 검증된 API 키
        
    Raises:
        HTTPException: 유효하지 않은 API 키
    """
    if header_value is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="X-API-KEY 헤더가 없습니다."
        )
    if not secrets.compare_digest(header_value, settings.API_KEY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API 키가 올바르지 않습니다."
        )
    return header_value
