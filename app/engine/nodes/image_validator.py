import httpx
import logging
from langchain_core.messages import HumanMessage, SystemMessage

from ..providers import ai_factory
from ..state import AiArticleState
from ..prompts import IMAGE_VALIDATOR_SYSTEM_PROMPT
from ..schemas import ImageValidationResponse
from app.utils.image import download_image_from_url, image_to_base64_url

logger = logging.getLogger(__name__)

chat_model = ai_factory.get_chat_model()
validator_llm = chat_model.with_structured_output(ImageValidationResponse)

async def image_validator_node(state: AiArticleState):
    """
    image_researcher_node에서 찾아낸 reference_image_url이 실제로
    문맥에 맞고 사용할 수 있는 유효한 이미지인지 멀티모달 모델을 통해 검증합니다.
    """
    final_url = state.get("reference_image_url")
    if final_url:
        final_url = final_url.strip('.,;:\'\"()[]{}<>')
        
    title = state.get("final_title", "")
    summary = " ".join(state.get("summary", []))

    if not final_url:
        logger.info("[ImageValidatorNode] No reference_image_url provided. Skipping validation.")
        return {"reference_image_url": None}

    logger.info(f"[ImageValidatorNode] Validating Reference URL: {final_url}")
    
    context = (
        f"Title: {title}\n"
        f"Summary: {summary}\n"
    )

    try:
        # 1. Download image to convert to base64 for reliable multi-modal LLM processing
        img = await download_image_from_url(final_url)
        if not img:
            logger.warning(f"[ImageValidatorNode] Failed to download or convert image from {final_url}")
            return {"reference_image_url": None}
            
        base64_url = image_to_base64_url(img)

        # 2. Extract structured response from LLM
        validator_content = [
            {"type": "text", "text": f"News context:\n{context}"},
            {"type": "image_url", "image_url": {"url": base64_url}}
        ]
        
        validator_res = await validator_llm.ainvoke([
            SystemMessage(content=IMAGE_VALIDATOR_SYSTEM_PROMPT),
            HumanMessage(content=validator_content)
        ])
        
        # 3. Analyze output
        if not validator_res.is_valid:
            logger.warning(f"[ImageValidatorNode] Rejected. Image URL: {final_url} Reason: {validator_res.reason}")
            return {"reference_image_url": None}
        else:
            logger.info(f"[ImageValidatorNode] Approved. Image URL: {final_url}")
            return {"reference_image_url": final_url}

    except httpx.RequestError as e:
        logger.error(f"[ImageValidatorNode] Failed to download image from {final_url}: {e}")
        return {"reference_image_url": None}
    except Exception as ve:
        logger.error(f"[ImageValidatorNode] Validation skipped/failed due to error: {ve}")
        return {"reference_image_url": None}
