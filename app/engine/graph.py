from langgraph.graph import StateGraph, END
from .state import ArticleState
from .nodes import analyze_node, select_editor_node, webtoon_creator_node, card_news_creator_node, webtoon_image_gen_node, card_news_image_gen_node, final_save_node

def route_by_content_type(state: ArticleState):
    """Router: content_type에 따라 경로 결정"""
    if state["content_type"] == "WEBTOON":
        return "webtoon"
    else:
        return "card_news"


def should_continue_webtoon(state: ArticleState):
    return "generate" if state.get("current_image_index", 0) < 4 else "save"


def create_graph():
    workflow = StateGraph(ArticleState)

    # 1. 노드 등록
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("select_editor", select_editor_node)
    workflow.add_node("webtoon_text", webtoon_creator_node)
    workflow.add_node("card_news_text", card_news_creator_node)
    workflow.add_node("webtoon_img", webtoon_image_gen_node)
    workflow.add_node("card_news_img", card_news_image_gen_node)
    workflow.add_node("final_save", final_save_node)

    # 2. 시작점 설정
    workflow.set_entry_point("analyze")

    # 3. 에디터 배정
    workflow.add_edge("analyze", "select_editor")
    
    # 4. 타입에 따라 분기
    workflow.add_conditional_edges(
        "select_editor",
        route_by_content_type,
        {
            "webtoon": "webtoon_text",
            "card_news": "card_news_text"
        }
    )

    # 5. 이미지 생성
    # 웹툰 경로
    workflow.add_edge("webtoon_text", "webtoon_img")
    workflow.add_conditional_edges(
        "webtoon_img",
        should_continue_webtoon,
        {"generate": "webtoon_img", "save": "final_save"}
    )

    # 카드뉴스 경로
    workflow.add_edge("card_news_text", "card_news_img")
    workflow.add_edge("card_news_img", "final_save")

    # 6. 종료
    workflow.add_edge("final_save", END)

    return workflow.compile()
