from langgraph.graph import StateGraph, END
from .state import GraphState
from .nodes import analyze_node, write_node, design_node

def create_graph():
    workflow = StateGraph(GraphState)

    # 노드 추가
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("write", write_node)
    workflow.add_node("design", design_node)

    # 엣지 연결 (순차적 실행)
    workflow.set_entry_point("analyze")
    workflow.add_edge("analyze", "write")
    workflow.add_edge("write", "design")
    workflow.add_edge("design", END)

    return workflow.compile()
