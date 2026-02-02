import io
import os
import shutil
from PIL import Image
from typing import Optional

from .s3 import upload_bytes_to_s3

def save_image_to_local(content_key: str, idx: int, img: Image.Image) -> str:
    """이미지 로컬 저장 공통 유틸"""
    folder_path = os.path.join("output", content_key)
    os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, f"{idx}.png")
    img.save(file_path)
    return file_path


def _image_to_png_bytes(img: Image.Image) -> bytes:
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def save_image_to_s3(content_key: str, idx: int, img: Image.Image) -> Optional[str]:
    """이미지를 S3에 바로 업로드"""
    s3_key = f"images/{content_key}/{idx}.png"
    png_bytes = _image_to_png_bytes(img)
    return upload_bytes_to_s3(s3_key, png_bytes, content_type="image/png")


def cleanup_local_reference_image_directory(content_key: str):
    """기준 이미지 파일이 위치한 디렉토리 삭제"""
    directory_path = os.path.join("output", content_key)
    if os.path.exists(directory_path):
        shutil.rmtree(directory_path)
