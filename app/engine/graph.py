from langgraph.graph import StateGraph, END
from .state import AiArticleState, TodayNewsnackState
from .nodes import (
    analyze_article_node,
    select_editor_node,
    content_creator_node,
    image_gen_node,
    save_ai_article_node,
    fetch_daily_briefing_articles_node,
    assemble_briefing_node,
    generate_audio_node,
    save_today_newsnack_node,
    image_research_agent_node,
)
from app.core.config import settings


def create_ai_article_graph():
    workflow = StateGraph(AiArticleState)

    # 1. 노드 등록
    workflow.add_node("analyze_article", analyze_article_node)
    workflow.add_node("image_research", image_research_agent_node)
    workflow.add_node("select_editor", select_editor_node)
    workflow.add_node("content_creator", content_creator_node)
    workflow.add_node("image_gen", image_gen_node)
    workflow.add_node("save_ai_article", save_ai_article_node)

    # 2. 시작점 설정
    workflow.set_entry_point("analyze_article")

    # 3. 엣지 연결
    def check_research_condition(_state: AiArticleState) -> str:
        if settings.AI_PROVIDER == "google" and settings.GOOGLE_IMAGE_WITH_REFERENCE:
            return "do_research"
        return "skip_research"

    workflow.add_conditional_edges(
        "analyze_article",
        check_research_condition,
        {"do_research": "image_research", "skip_research": "select_editor"}
    )
    workflow.add_edge("image_research", "select_editor")
    workflow.add_edge("select_editor", "content_creator")
    workflow.add_edge("content_creator", "image_gen")
    workflow.add_edge("image_gen", "save_ai_article")
    workflow.add_edge("save_ai_article", END)

    return workflow.compile()


def create_today_newsnack_graph():
    workflow = StateGraph(TodayNewsnackState)

    # 노드 등록
    workflow.add_node("fetch_articles", fetch_daily_briefing_articles_node)
    workflow.add_node("assemble_briefing", assemble_briefing_node)
    workflow.add_node("generate_audio", generate_audio_node)
    workflow.add_node("save_today_newsnack", save_today_newsnack_node)

    # 엣지 연결
    workflow.set_entry_point("fetch_articles")
    workflow.add_edge("fetch_articles", "assemble_briefing")
    workflow.add_edge("assemble_briefing", "generate_audio")
    workflow.add_edge("generate_audio", "save_today_newsnack")
    workflow.add_edge("save_today_newsnack", END)

    return workflow.compile()
