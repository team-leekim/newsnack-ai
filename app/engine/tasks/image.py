import base64
import logging
from io import BytesIO

from PIL import Image
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_random_exponential

from ..providers import ai_factory
from ..prompts import ImageStyle, create_image_prompt, create_google_image_prompt
from app.core.config import settings

logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, min=2, max=10)
)
async def generate_openai_image_task(idx: int, prompt: str, content_type: str) -> Image.Image:
    """OpenAI를 사용한 개별 이미지 생성 (재시도 포함)"""
    client = ai_factory.get_image_client()
    style = ImageStyle.get_style(content_type)
    final_prompt = create_image_prompt(style, prompt)

    try:
        response = await client.images.generate(
            model=settings.OPENAI_IMAGE_MODEL,
            prompt=final_prompt,
            n=1,
            quality="low",
            size="1024x1024"
        )

        b64_data = response.data[0].b64_json
        img_data = base64.b64decode(b64_data)
        img = Image.open(BytesIO(img_data))

        return img

    except Exception as e:
        logger.error(f"Error generating OpenAI image {idx}: {e}")
        raise


@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, min=2, max=10)
)
async def generate_google_image_task(idx: int, prompt: str, content_type: str, ref_image: Image.Image = None) -> Image.Image:
    """Gemini를 사용한 개별 이미지 생성 (재시도 포함, 메모리 기반 참조)"""
    client = ai_factory.get_image_client()
    style = ImageStyle.get_style(content_type)

    with_reference = bool(ref_image is not None)
    final_prompt = create_google_image_prompt(
        style=style,
        prompt=prompt,
        content_type=content_type,
        with_reference=with_reference
    )
    contents = [final_prompt]

    if with_reference:
        contents.append(ref_image)

    image_model = (
        settings.GOOGLE_IMAGE_MODEL_WITH_REFERENCE
        if settings.GOOGLE_IMAGE_WITH_REFERENCE
        else settings.GOOGLE_IMAGE_MODEL
    )

    config_params = {"aspect_ratio": "1:1"}
    if settings.GOOGLE_IMAGE_WITH_REFERENCE:
        config_params["image_size"] = "1K"
    image_config = types.ImageConfig(**config_params)

    try:
        response = await client.aio.models.generate_content(
            model=image_model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=['IMAGE'],
                image_config=image_config
            )
        )
        img_part = next((part.inline_data for part in response.parts if part.inline_data), None)
        if img_part:
            img = Image.open(BytesIO(img_part.data))
            return img
        else:
            raise ValueError(f"No image data in response for image {idx}")

    except Exception as e:
        logger.error(f"Error generating image {idx}: {e}")
        raise
