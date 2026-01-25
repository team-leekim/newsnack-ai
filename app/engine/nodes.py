import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from .state import ArticleState, AnalysisResponse, EditorContentResponse
import json
import random
from google import genai
from google.genai import types
from PIL import Image
import asyncio


# 스타일 래퍼 정의
WEBTOON_STYLE = "Modern digital webtoon art style, clean lines, vibrant cel-shading, high-quality anime aesthetic, "
CARDNEWS_STYLE = "Minimalist flat vector illustration, Instagram aesthetic, soft pastel tones, clean corporate design, "

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", google_api_key=os.environ["GOOGLE_API_KEY"])
client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

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
    """뉴스 분석, 키워드 추출 및 타입 분류"""
    article = state['raw_article']
    
    prompt = f"""
    다음 뉴스를 분석해서 핵심 요약 3줄, 키워드(최대 5개),
    그리고 콘텐츠 타입(WEBTOON 또는 CARD_NEWS)을 결정해줘.
    내용 요약과 키워드는 반드시 한국어로 작성해야 해.

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
    """웹툰 스타일 본문 및 이미지 프롬프트 생성"""
    editor = state['editor']
    article = state['raw_article']
    
    system_msg = SystemMessage(content=f"""
    {editor['persona_prompt']}
    너는 지금부터 이 뉴스를 '웹툰' 형식의 대본으로 재구성해야 해. 
    기승전결이 뚜렷하게 한국어로 작성해줘. 
    독자들이 흥미를 느낄 수 있도록 에디터의 말투를 활용해.
    """)
    human_msg = HumanMessage(content=f"제목: {article['title']}\n내용: {article['content']}")
    
    response = editor_llm.invoke([system_msg, human_msg])
    
    return {
        "final_title": response.final_title,
        "final_body": response.final_body,
        "image_prompts": response.image_prompts
    }


def card_news_creator_node(state: ArticleState):
    """카드뉴스 스타일 본문 및 이미지 프롬프트 생성"""
    editor = state['editor']
    article = state['raw_article']
    
    system_msg = SystemMessage(content=f"{editor['persona_prompt']}\n너는 지금부터 이 뉴스를 '카드뉴스' 형식으로 재구성해야 해. 정보를 전달하기 쉽고 명확하게 요약해서 작성해줘.")
    system_msg = SystemMessage(content=f"""
    {editor['persona_prompt']}
    너는 지금부터 이 뉴스를 '카드뉴스' 형식으로 재구성해야 해.
    정보를 전달하기 쉽고 명확하게 한글로 요약해서 작성해줘.
    """)
    human_msg = HumanMessage(content=f"제목: {article['title']}\n내용: {article['content']}")
    
    response = editor_llm.invoke([system_msg, human_msg])
    
    return {
        "final_title": response.final_title,
        "final_body": response.final_body,
        "image_prompts": response.image_prompts
    }


def save_local_image(article_id, idx, img):
    """이미지 저장 공통 유틸"""
    folder_path = f"output/{article_id}"
    os.makedirs(folder_path, exist_ok=True)
    file_path = f"{folder_path}/image_{idx}.png"
    img.save(file_path)
    return file_path


def webtoon_image_gen_node(state: ArticleState):
    """[순차 루프] 웹툰은 1번 이미지를 참조하여 일관성 유지"""
    idx = state.get("current_image_index", 0)

    instruction = "Ensure the Korean text in the speech bubble is clear and legible. Use a simple comic font."
    full_prompt = f"{WEBTOON_STYLE} {state['image_prompts'][idx]}. Ensure consistent character appearance. {instruction}"

    image_urls = state.get("image_urls", [])
    
    print(f"--- 웹툰 이미지 생성 중 ({idx + 1}/4) ---")
    
    contents = [full_prompt]
    # 2번째 이미지부터는 1번 이미지를 스타일 참조
    if idx > 0 and image_urls:
        contents.append(Image.open(image_urls[0]))
        
    response = client.models.generate_content(
        model="gemini-3-pro-image-preview", #TODO: 모델명 분리
        contents=contents,
        config=types.GenerateContentConfig(response_modalities=['IMAGE'])
    )
    
    img = next((part.as_image() for part in response.parts if part.inline_data), None)
    if img:
        path = save_local_image(state['raw_article']['id'], idx, img)
        return {"image_urls": image_urls + [path], "current_image_index": idx + 1}
    return {"current_image_index": idx + 1}


async def generate_single_cardnews(article_id, idx, prompt):
    """카드뉴스 개별 생성 (비동기)"""
    instruction = "Focus on a clean infographic layout. If there's Korean text, make it bold and centered. Keep the background simple for readability."
    full_prompt = f"{CARDNEWS_STYLE} {prompt}. {instruction}"

    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash-image", #TODO: 모델명 분리
        contents=[full_prompt],
        config=types.GenerateContentConfig(response_modalities=['IMAGE'])
    )
    img = next((part.as_image() for part in response.parts if part.inline_data), None)
    if img:
        return save_local_image(article_id, idx, img)
    return None


def card_news_image_gen_node(state: ArticleState):
    """[병렬 처리] 카드뉴스는 속도 우선, 4장 동시 생성"""
    print(f"--- 카드뉴스 이미지 4장 병렬 생성 시작 ---")
    article_id = state['raw_article']['id']
    prompts = state['image_prompts']
    
    # 비동기 루프 실행
    loop = asyncio.get_event_loop()
    tasks = [generate_single_cardnews(article_id, i, prompts[i]) for i in range(4)]
    paths = loop.run_until_complete(asyncio.gather(*tasks))
    
    valid_paths = [p for p in paths if p]
    return {"image_urls": valid_paths}


def final_save_node(state: ArticleState):
    """최종 결과를 JSON으로 저장"""
    import json
    article_id = state['raw_article']['id']
    output_data = {
        "article_id": article_id,
        "content_type": state["content_type"],
        "editor": state["editor"]["name"],
        "title": state["final_title"],
        "body": state["final_body"],
        "summary": state["summary"],
        "keywords": state["keywords"],
        "images": state["image_urls"]
    }
    
    file_path = f"output/{article_id}/content.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
        
    print(f"--- 최종 결과 저장 완료: {file_path} ---")
    return state
