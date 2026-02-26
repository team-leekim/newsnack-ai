from langgraph.graph import StateGraph, END
from .state import AiArticleState, TodayNewsnackState
from .nodes import (
    analyze_article,
    select_editor,
    draft_article,
    generate_images,
    save_ai_article,
    fetch_articles,
    assemble_briefing,
    generate_audio,
    save_today_newsnack,
    image_researcher,
    validate_image,
)
from app.core.config import settings


def create_ai_article_graph():
    workflow = StateGraph(AiArticleState)

    # 노드 등록
    workflow.add_node("analyze_article", analyze_article)
    workflow.add_node("image_researcher", image_researcher)
    workflow.add_node("validate_image", validate_image)
    workflow.add_node("select_editor", select_editor)
    workflow.add_node("draft_article", draft_article)
    workflow.add_node("generate_images", generate_images)
    workflow.add_node("save_ai_article", save_ai_article)

    # 시작점 설정
    workflow.set_entry_point("analyze_article")

    def check_research_condition(_state: AiArticleState) -> str:
        if settings.AI_PROVIDER == "google" and settings.GOOGLE_IMAGE_WITH_REFERENCE:
            return "do_research"
        return "skip_research"

    # 엣지 연결
    workflow.add_conditional_edges(
        "analyze_article",
        check_research_condition,
        {"do_research": "image_researcher", "skip_research": "select_editor"}
    )
    workflow.add_edge("image_researcher", "validate_image")
    workflow.add_edge("validate_image", "select_editor")
    workflow.add_edge("select_editor", "draft_article")
    workflow.add_edge("draft_article", "generate_images")
    workflow.add_edge("generate_images", "save_ai_article")
    workflow.add_edge("save_ai_article", END)

    return workflow.compile()


def create_today_newsnack_graph():
    workflow = StateGraph(TodayNewsnackState)

    # 노드 등록
    workflow.add_node("fetch_articles", fetch_articles)
    workflow.add_node("assemble_briefing", assemble_briefing)
    workflow.add_node("generate_audio", generate_audio)
    workflow.add_node("save_today_newsnack", save_today_newsnack)

    # 엣지 연결
    workflow.set_entry_point("fetch_articles")
    workflow.add_edge("fetch_articles", "assemble_briefing")
    workflow.add_edge("assemble_briefing", "generate_audio")
    workflow.add_edge("generate_audio", "save_today_newsnack")
    workflow.add_edge("save_today_newsnack", END)

    return workflow.compile()
