import re
import logging
from langchain_core.messages import HumanMessage
from langchain.agents import create_agent

from ..providers import ai_factory
from ..state import AiArticleState
from ..prompts import IMAGE_RESEARCH_SYSTEM_PROMPT
from ..tasks.search import get_company_logo, get_person_thumbnail, get_general_image

logger = logging.getLogger(__name__)

tools = [get_company_logo, get_person_thumbnail, get_general_image]

def _get_agent():
    chat_model = ai_factory.get_chat_model()
    return create_agent(chat_model, tools=tools, system_prompt=IMAGE_RESEARCH_SYSTEM_PROMPT)

async def image_research_agent_node(state: AiArticleState):
    """
    뉴스 기사의 핵심 엔티티를 파악하고, 최적의 참조 이미지를 검색하여 URL을 반환하는 에이전트 노드.
    설정에 따라 조건부로 실행됩니다.
    """
    title = state.get("final_title", "")
    summary = " ".join(state.get("summary", []))
    
    logger.info(f"[ImageResearchAgent] Starting research for article: {title}")
    
    agent = _get_agent()
    
    context = (
        f"Title: {title}\n"
        f"Summary: {summary}\n"
        "Find the best reference image URL for this news."
    )
    
    try:
        response = await agent.ainvoke({"messages": [HumanMessage(content=context)]})
        final_message = response["messages"][-1].content.strip()
        
        if final_message == "NONE":
            final_url = None
        else:
            url_match = re.search(r'(https?://[^\s]+)', final_message)
            if url_match:
                final_url = url_match.group(1)
            else:
                final_url = None
                logger.warning(f"[ImageResearchAgent] Could not parse URL from response: {final_message}")

        logger.info(f"[ImageResearchAgent] Chosen Reference URL: {final_url}")
        return {"reference_image_url": final_url}
        
    except Exception as e:
        logger.error(f"[ImageResearchAgent] Agent execution failed: {e}")
        return {"reference_image_url": None}
