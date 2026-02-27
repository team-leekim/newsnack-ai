import io
import os
import shutil
import base64
from PIL import Image
from typing import Optional
import httpx
import logging
from tenacity import retry, stop_after_attempt, wait_exponential

from .s3 import s3_manager
from app.core.config import settings

logger = logging.getLogger(__name__)

def save_image_to_local(content_key: str, idx: int, img: Image.Image) -> str:
    """이미지 로컬 저장 공통 유틸"""
    folder_path = os.path.join("output", content_key)
    os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, f"{idx}.png")
    img.save(file_path)
    return file_path


def _image_to_bytes(img: Image.Image, img_format: str = None) -> bytes:
    """PIL Image를 지정된 포맷의 바이트로 변환합니다. 지정되지 않으면 이미지 원본 포맷이나 JPEG를 사용합니다."""
    fmt = img_format or img.format or "JPEG"
    buffer = io.BytesIO()
    img.save(buffer, format=fmt)
    return buffer.getvalue()


def image_to_base64_url(img: Image.Image) -> str:
    """PIL Image를 원래 포맷에 맞는 base64 data URL로 변환합니다."""
    fmt = img.format if img.format else "JPEG"
    img_bytes = _image_to_bytes(img, fmt)
    b64_str = base64.b64encode(img_bytes).decode("utf-8")
    return f"data:image/{fmt.lower()};base64,{b64_str}"


def pil_to_base64(img: Image.Image, img_format: str = "PNG") -> str:
    """PIL Image를 지정된 포맷의 일반 base64 문자열로 변환합니다. (OpenAI API 등에 사용)"""
    buffered = io.BytesIO()
    img.save(buffered, format=img_format)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


async def upload_image_to_s3(content_key: str, idx: int, img: Image.Image) -> Optional[str]:
    """이미지를 S3에 바로 업로드"""
    s3_key = f"images/{content_key}/{idx}.png"
    png_bytes = _image_to_bytes(img, "PNG")
    return await s3_manager.upload_bytes(s3_key, png_bytes, content_type="image/png")


def cleanup_local_reference_image_directory(content_key: str):
    """기준 이미지 파일이 위치한 디렉토리 삭제"""
    directory_path = os.path.join("output", content_key)
    if os.path.exists(directory_path):
        shutil.rmtree(directory_path)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def _fetch_image(url: str, headers: dict) -> Image.Image:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, headers=headers, follow_redirects=True)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))
        
        # PIL이 원본 포맷을 인식하지 못했을 경우 HTTP 헤더에서 추론
        original_format = img.format
        if not original_format:
            content_type = resp.headers.get("content-type", "").lower()
            if "png" in content_type:
                original_format = "PNG"
            elif "webp" in content_type:
                original_format = "WEBP"
            else:
                original_format = "JPEG"
                
        img = img.convert("RGB")
        img.format = original_format
        return img


async def download_image_from_url(url: str) -> Optional[Image.Image]:
    """주어진 URL에서 이미지를 다운로드하여 PIL Image 반환 (재시도 포함)"""
    try:
        headers = {"User-Agent": settings.USER_AGENT}
        return await _fetch_image(url, headers)
    except Exception as e:
        logger.error(f"[download_image_from_url] Failed to download {url} after retries: {e}")
        # 실패 시 상위에서 처리하도록 None 반환
    return None
