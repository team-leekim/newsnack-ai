from langgraph.graph import StateGraph, END
from .state import ArticleState
from .nodes import (
    analyze_node, 
    select_editor_node, 
    webtoon_creator_node, 
    card_news_creator_node,
    image_gen_node,
    final_save_node
)

def should_continue_webtoon(state: ArticleState):
    return "generate" if state.get("current_image_index", 0) < 4 else "save"


def create_graph():
    workflow = StateGraph(ArticleState)

    # 1. 노드 등록
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("select_editor", select_editor_node)
    workflow.add_node("webtoon_text", webtoon_creator_node)
    workflow.add_node("card_news_text", card_news_creator_node)
    workflow.add_node("image_gen", image_gen_node)
    workflow.add_node("final_save", final_save_node)

    # 2. 시작점 설정
    workflow.set_entry_point("analyze")

    # 3. 에디터 배정
    workflow.add_edge("analyze", "select_editor")
    
    # 4. 콘텐츠 타입별 프롬프트 생성
    workflow.add_conditional_edges(
        "select_editor",
        lambda x: "webtoon" if x["content_type"] == "WEBTOON" else "card_news",
        {"webtoon": "webtoon_text", "card_news": "card_news_text"}
    )

    # 5. 이미지 생성
    workflow.add_edge("webtoon_text", "image_gen")
    workflow.add_edge("card_news_text", "image_gen")
    
    workflow.add_edge("image_gen", "final_save")
    workflow.add_edge("final_save", END)

    return workflow.compile()
