from langgraph.graph import StateGraph, END
from .state import ArticleState
from .nodes import analyze_node, webtoon_creator_node, card_news_creator_node

def route_by_content_type(state: ArticleState):
    """Router: content_type에 따라 경로 결정"""
    if state["content_type"] == "WEBTOON":
        return "webtoon"
    else:
        return "card_news"

def create_graph():
    workflow = StateGraph(ArticleState)

    # 노드 등록
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("webtoon", webtoon_creator_node)
    workflow.add_node("card_news", card_news_creator_node)

    # 엣지 연결
    workflow.set_entry_point("analyze")
    
    # 조건부 엣지 추가
    workflow.add_conditional_edges(
        "analyze",
        route_by_content_type,
        {
            "webtoon": "webtoon",
            "card_news": "card_news"
        }
    )

    workflow.add_edge("webtoon", END)
    workflow.add_edge("card_news", END)

    return workflow.compile()
