import re
import logging
from langchain_core.messages import HumanMessage
from langchain.agents import create_agent

from ..providers import ai_factory
from ..state import AiArticleState
from ..prompts import IMAGE_RESEARCHER_SYSTEM_PROMPT
from ..tasks.search import get_company_logo, get_person_thumbnail, get_fallback_image

logger = logging.getLogger(__name__)

tools = [get_company_logo, get_person_thumbnail, get_fallback_image]

chat_model = ai_factory.get_chat_model()
research_agent = create_agent(chat_model, tools=tools, system_prompt=IMAGE_RESEARCHER_SYSTEM_PROMPT)

async def image_researcher_node(state: AiArticleState):
    """
    뉴스 기사의 핵심 엔티티를 파악하고, 최적의 참조 이미지를 검색하여 URL을 반환하는 에이전트 노드.
    설정에 따라 조건부로 실행됩니다.
    """
    title = state.get("final_title", "")
    summary = " ".join(state.get("summary", []))
    
    logger.info(f"[ImageResearchAgent] Starting research for article: {title}")
    
    context = (
        f"Title: {title}\n"
        f"Summary: {summary}\n"
        "Find the best reference image URL for this news."
    )
    
    try:
        response = await research_agent.ainvoke({"messages": [HumanMessage(content=context)]})
        messages = response["messages"]

        # 디버그: 전체 메시지 타입 및 content 덤프
        for i, msg in enumerate(messages):
            content_str = str(msg.content) if msg.content else ""
            content_preview = content_str[:120].replace("\n", " ")
            logger.debug(f"[ImageResearchAgent] msg[{i}] type={type(msg).__name__}, content='{content_preview}'")

        # create_agent는 마지막 AIMessage가 빈 content를 가질 수 있으므로
        # 메시지 전체를 역순 탐색하여 URL이 포함된 첫 번째 메시지를 찾음
        final_url = None
        for msg in reversed(messages):
            content = str(msg.content) if msg.content else ""
            if content.strip() == "NONE":
                final_url = None
                break
            url_match = re.search(r'(https?://[^\s\'"<>{}]+)', content)
            if url_match:
                final_url = url_match.group(1)
                break

        if final_url is None:
            logger.warning(f"[ImageResearchAgent] No URL found in any message after full traversal.")

        logger.info(f"[ImageResearchAgent] Chosen Reference URL: {final_url}")
        return {"reference_image_url": final_url}

    except Exception as e:
        logger.error(f"[ImageResearchAgent] Agent execution failed: {e}")
        return {"reference_image_url": None}
