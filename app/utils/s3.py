import boto3
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

def _create_s3_client():
    client_kwargs = {}
    client_kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
    client_kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
    client_kwargs["region_name"] = settings.AWS_REGION
    return boto3.client("s3", **client_kwargs)


def _build_s3_url(bucket: str, key: str, region: Optional[str]) -> str:
    if region:
        return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
    return f"https://{bucket}.s3.amazonaws.com/{key}"


def upload_bytes_to_s3(s3_key: str, data: bytes, content_type: Optional[str] = None) -> Optional[str]:
    bucket = settings.AWS_S3_BUCKET
    client = _create_s3_client()

    try:
        put_kwargs = {"Bucket": bucket, "Key": s3_key, "Body": data}
        if content_type:
            put_kwargs["ContentType"] = content_type
        client.put_object(**put_kwargs)
        return _build_s3_url(bucket, s3_key, client.meta.region_name)
    except Exception as e:
        logger.error(f"S3 upload failed: {s3_key} ({e})")
        return None
