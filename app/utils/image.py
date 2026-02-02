import os
from PIL import Image    

def save_local_image(content_key: str, idx: int, img: Image.Image) -> str:
    """이미지 로컬 저장 공통 유틸"""
    folder_path = os.path.join("output", content_key)
    os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, f"{idx}.png")
    img.save(file_path)
    return file_path
