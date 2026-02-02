import aioboto3
import logging
from typing import Optional
from botocore.exceptions import ClientError
from app.core.config import settings

logger = logging.getLogger(__name__)

class S3ClientManager:
    """S3 클라이언트 세션을 관리하는 팩토리 클래스"""
    def __init__(self):
        self._session = None

    def _get_session(self):
        if not self._session:
            self._session = aioboto3.Session(
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION,
            )
        return self._session

    async def upload_bytes(self, s3_key: str, data: bytes, content_type: Optional[str] = None) -> Optional[str]:
        bucket = settings.AWS_S3_BUCKET
        session = self._get_session()
        
        try:
            # 클라이언트를 비동기적으로 생성 및 반환
            async with session.client("s3") as s3_client:
                put_kwargs = {"Bucket": bucket, "Key": s3_key, "Body": data}
                if content_type:
                    put_kwargs["ContentType"] = content_type
                
                await s3_client.put_object(**put_kwargs)
                
                # URL 생성 로직
                url = f"https://{bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"
                return url
        except ClientError as e:
            logger.error(f"S3 upload ClientError: {s3_key} ({e})")
            return None
        except Exception as e:
            logger.error(f"S3 upload Unexpected Error: {s3_key} ({e})")
            return None

# 전역 인스턴스 생성
s3_manager = S3ClientManager()
