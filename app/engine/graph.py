from langgraph.graph import StateGraph, END
from .state import ArticleState
from .nodes import analyze_node, select_editor_node, webtoon_creator_node, card_news_creator_node, image_gen_node

def route_by_content_type(state: ArticleState):
    """Router: content_type에 따라 경로 결정"""
    if state["content_type"] == "WEBTOON":
        return "webtoon"
    else:
        return "card_news"


def should_continue_gen(state: ArticleState):
    """이미지를 4장 다 만들었는지 확인하는 조건문"""
    if state["current_image_index"] < 4:
        return "generate"
    return "end"


def create_graph():
    workflow = StateGraph(ArticleState)

    # 1. 노드 등록
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("select_editor", select_editor_node)
    workflow.add_node("webtoon", webtoon_creator_node)
    workflow.add_node("card_news", card_news_creator_node)
    workflow.add_node("image_gen", image_gen_node)

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

    # 5. 이미지 생성
    workflow.add_edge("webtoon", "image_gen")
    workflow.add_edge("card_news", "image_gen")
    
    # 6. 루프 또는 종료
    workflow.add_conditional_edges(
        "image_gen",
        should_continue_gen,
        {
            "generate": "image_gen",
            "end": END
        }
    )

    return workflow.compile()
