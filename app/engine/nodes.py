import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from .state import GraphState, AnalysisResponse, ImagePromptResponse

# 모델 설정
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.environ["GOOGLE_API_KEY"])
analyze_llm = llm.with_structured_output(AnalysisResponse)
design_llm = llm.with_structured_output(ImagePromptResponse)

def analyze_node(state: GraphState):
    """뉴스 요약 및 콘텐츠 타입 결정"""
    article = state['raw_article']
    
    prompt = f"""
    다음 뉴스를 분석해서 3줄로 요약하고, 가장 적합한 콘텐츠 타입을 결정해줘.
    
    제목: {article['title']}
    본문: {article['content']}
    """

    response = analyze_llm.invoke(prompt)
    
    return {
        "summary": response.summary, 
        "content_type": response.content_type
    }

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
    prompt = f"다음 뉴스 대본을 바탕으로 이미지 생성 프롬프트 4개를 만들어줘: {script}"

    response = design_llm.invoke(prompt)

    return {"image_prompts": response.prompts}
