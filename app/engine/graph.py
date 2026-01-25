from langgraph.graph import StateGraph, END
from .state import ArticleState
from .nodes import analyze_node, select_editor_node, webtoon_creator_node, card_news_creator_node

def route_by_content_type(state: ArticleState):
    """Router: content_type에 따라 경로 결정"""
    if state["content_type"] == "WEBTOON":
        return "webtoon"
    else:
        return "card_news"

def create_graph():
    workflow = StateGraph(ArticleState)

    # 1. 노드 등록
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("select_editor", select_editor_node)
    workflow.add_node("webtoon", webtoon_creator_node)
    workflow.add_node("card_news", card_news_creator_node)

    # 2. 시작점 설정
    workflow.set_entry_point("analyze")

    # 3. 에디터 배정
    workflow.add_edge("analyze", "select_editor")
    
    # 4. 타입에 따라 분기
    workflow.add_conditional_edges(
        "select_editor",
        route_by_content_type,
        {
            "webtoon": "webtoon",
            "card_news": "card_news"
        }
    )

    # 5. 종료
    workflow.add_edge("webtoon", END)
    workflow.add_edge("card_news", END)

    return workflow.compile()
