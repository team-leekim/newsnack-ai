import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from .state import ArticleState, AnalysisResponse, EditorContentResponse
import json
import random

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GOOGLE_API_KEY"))

# 구조화된 출력용 LLM
analyze_llm = llm.with_structured_output(AnalysisResponse)
editor_llm = llm.with_structured_output(EditorContentResponse)


def load_editors():
    with open("data/editors.json", "r", encoding="utf-8") as f:
        return json.load(f)


def select_editor_node(state: ArticleState):
    """분류된 타입에 맞는 에디터를 JSON 데이터에서 선택"""
    editors = load_editors()
    target_type = state["content_type"]
    
    candidates = [e for e in editors if e["type"] == target_type]
    selected = random.choice(candidates if candidates else editors)
    
    return {"editor": selected}


def analyze_node(state: ArticleState):
    """Node 2 & 3: 뉴스 분석, 키워드 추출 및 타입 분류"""
    article = state['raw_article']
    
    prompt = f"""
    다음 뉴스를 분석해서 핵심 요약 3줄, 키워드(최대 5개),
    그리고 콘텐츠 타입(WEBTOON 또는 CARD_NEWS)을 결정해줘.
    
    제목: {article['title']}
    본문: {article['content']}
    """
    
    response = analyze_llm.invoke(prompt)
    
    return {
        "summary": response.summary,
        "keywords": response.keywords,
        "content_type": response.content_type
    }


def webtoon_creator_node(state: ArticleState):
    """Node 5A: 웹툰 스타일 본문 및 이미지 프롬프트 생성"""
    editor = state['editor']
    article = state['raw_article']
    
    system_msg = SystemMessage(content=f"{editor['persona_prompt']}\n너는 지금부터 이 뉴스를 '웹툰' 형식의 대본으로 재구성해야 해. 기승전결이 뚜렷하고 재미있게 작성해줘.")
    human_msg = HumanMessage(content=f"제목: {article['title']}\n내용: {article['content']}")
    
    response = editor_llm.invoke([system_msg, human_msg])
    
    return {
        "final_title": response.final_title,
        "final_body": response.final_body,
        "image_prompts": response.image_prompts
    }


def card_news_creator_node(state: ArticleState):
    """Node 5B: 카드뉴스 스타일 본문 및 이미지 프롬프트 생성"""
    editor = state['editor']
    article = state['raw_article']
    
    system_msg = SystemMessage(content=f"{editor['persona_prompt']}\n너는 지금부터 이 뉴스를 '카드뉴스' 형식으로 재구성해야 해. 정보를 전달하기 쉽고 명확하게 요약해서 작성해줘.")
    human_msg = HumanMessage(content=f"제목: {article['title']}\n내용: {article['content']}")
    
    response = editor_llm.invoke([system_msg, human_msg])
    
    return {
        "final_title": response.final_title,
        "final_body": response.final_body,
        "image_prompts": response.image_prompts
    }