import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from .state import GraphState

# 모델 설정
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GOOGLE_API_KEY"))

def analyze_node(state: GraphState):
    """뉴스 요약 및 콘텐츠 타입 결정"""
    article = state['raw_article']
    
    prompt = f"""
    다음 뉴스를 분석해서 3줄로 요약하고, 이 뉴스가 'WEBTOON'(스토리 중심)과 'CARD_NEWS'(정보 중심) 중 
    어느 형식에 적합한지 결정해줘.
    
    뉴스 제목: {article['title']}
    뉴스 본문: {article['content']}
    
    반드시 아래 형식을 지켜서 응답해:
    요약1: ...
    요약2: ...
    요약3: ...
    타입: WEBTOON 또는 CARD_NEWS
    """
    
    response = llm.invoke(prompt)
    content = response.content
    
    # 간단한 파싱 (#TODO: Pydantic으로 변경)
    lines = content.split('\n')
    summary = [line for line in lines if line.startswith('요약')]
    content_type = "WEBTOON" if "WEBTOON" in content else "CARD_NEWS"
    
    return {"summary": summary, "content_type": content_type}

def write_node(state: GraphState):
    """에디터 페르소나 적용 본문 작성"""
    editor = state['editor']
    summary = state['summary']
    
    system_msg = SystemMessage(content=editor['persona_prompt'])
    human_msg = HumanMessage(content=f"다음 요약된 뉴스 내용을 바탕으로 너의 말투로 뉴스 본문을 다시 써줘: {summary}")
    
    response = llm.invoke([system_msg, human_msg])
    
    return {"final_script": response.content}

def design_node(state: GraphState):
    """이미지 생성을 위한 프롬프트 추출"""
    script = state['final_script']
    
    prompt = f"""
    다음 뉴스 대본을 바탕으로, 총 4장의 웹툰/카드뉴스를 만들 거야. 
    각 장면에 어울리는 구체적인 이미지 생성 프롬프트(영문)를 4개 리스트로 만들어줘.
    
    대본: {script}
    """
    
    response = llm.invoke(prompt)
    # 임시로 라인별 분리
    prompts = response.content.split('\n')[:4]
    
    return {"image_prompts": prompts}
