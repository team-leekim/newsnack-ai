import logging
from io import BytesIO
from PIL import Image
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_random_exponential

from ..providers import ai_factory
from ..prompts import ImageStyle, create_image_prompt
from app.core.config import settings
from app.utils.image import pil_to_base64, base64_to_pil
from app.engine.circuit_breaker import with_circuit_breaker

logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, min=2, max=10)
)
async def generate_openai_image_task(idx: int, prompt: str, content_type: str, ref_image: Image.Image = None, ref_type: str = "style") -> Image.Image:
    """OpenAI를 사용한 개별 이미지 생성 (참조/재시도 지원)"""
    client = ai_factory.get_image_client()
    style = ImageStyle.get_style(content_type)
    
    ref_image_provided = bool(ref_image is not None)
    final_prompt = create_image_prompt(
        style=style, 
        prompt=prompt, 
        content_type=content_type, 
        ref_image_provided=ref_image_provided,
        ref_type=ref_type
    )

    try:
        content_items = [{"type": "input_text", "text": final_prompt}]
        
        if ref_image:
            b64_img = pil_to_base64(ref_image, "PNG")
            content_items.append({
                "type": "input_image",
                "image_url": f"data:image/png;base64,{b64_img}"
            })

        response = await client.responses.create(
            model=settings.OPENAI_CHAT_MODEL,
            input=[{
                "role": "user",
                "content": content_items
            }],
            tools=[{
                "type": "image_generation",
                "action": "auto",
                "quality": settings.OPENAI_IMAGE_QUALITY,
                "size": settings.OPENAI_IMAGE_SIZE,
            }],
        )
        
        image_generation_calls = [
            output for output in response.output
            if output.type == "image_generation_call"
        ]
        
        if not image_generation_calls:
            raise ValueError(f"No image_generation_call found in response for image {idx}")
            
        b64_data = image_generation_calls[0].result

        return base64_to_pil(b64_data)

    except Exception as e:
        logger.error(f"[GenerateOpenaiImageTask] Error generating OpenAI image {idx}: {e}")
        raise


@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, min=2, max=10)
)
@with_circuit_breaker(
    circuit_id="google_image_api",
    failure_window_secs=300,
    recovery_timeout_secs=600,
    fallback_kwargs={
        "override_model_name": settings.GOOGLE_IMAGE_MODEL_FALLBACK,
        "override_image_size": settings.GOOGLE_IMAGE_MODEL_FALLBACK_SIZE
    }
)
async def generate_google_image_task(idx: int, prompt: str, content_type: str, ref_image: Image.Image = None, ref_type: str = "style",
                                     override_model_name: str = None, override_image_size: str = None) -> Image.Image:
    """Gemini를 사용한 개별 이미지 생성 (참조/재시도/서킷 브레이커 지원)"""
    client = ai_factory.get_image_client()
    style = ImageStyle.get_style(content_type)

    ref_image_provided = bool(ref_image is not None)
    final_prompt = create_image_prompt(
        style=style,
        prompt=prompt,
        content_type=content_type,
        ref_image_provided=ref_image_provided,
        ref_type=ref_type
    )
    contents = [final_prompt]

    if ref_image:
        contents.append(ref_image)

    model_name = override_model_name or settings.GOOGLE_IMAGE_MODEL_PRIMARY
    image_size = override_image_size or settings.GOOGLE_IMAGE_MODEL_PRIMARY_SIZE
    
    config_params = {
        "aspect_ratio": settings.GOOGLE_IMAGE_ASPECT_RATIO,
        "image_size": image_size
    }
    image_config = types.ImageConfig(**config_params)

    try:
        response = await client.aio.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=['IMAGE'],
                image_config=image_config
            )
        )
    except Exception as e:
        logger.error(f"[GenerateGoogleImageTask] Error generating image {idx}: {e}")
        raise

    if not response.parts:
        reason = "UNKNOWN"
        
        # Check if it was blocked at the prompt level
        prompt_feedback = getattr(response, 'prompt_feedback', None)
        if prompt_feedback and getattr(prompt_feedback, 'block_reason', None):
            block_reason = prompt_feedback.block_reason
            reason = f"PROMPT_BLOCKED ({getattr(block_reason, 'name', str(block_reason))})"
            message = getattr(prompt_feedback, 'block_reason_message', None)
            if message:
                reason += f" - {message}"
            
        # Check if it was blocked at the candidate level
        elif getattr(response, 'candidates', None):
            candidate = response.candidates[0]
            finish_reason = getattr(candidate, 'finish_reason', None)
            if finish_reason:
                reason = getattr(finish_reason, 'name', str(finish_reason))
                finish_message = getattr(candidate, 'finish_message', None)
                if finish_message:
                    reason += f" - {finish_message}"
                
        raise ValueError(f"Gemini API returned empty parts for image {idx}. Reason: {reason}")

    img_part = next((part.inline_data for part in response.parts if part.inline_data), None)
    if img_part:
        img = Image.open(BytesIO(img_part.data))
        return img
    else:
        raise ValueError(f"No inline_data found in response parts for image {idx}")
