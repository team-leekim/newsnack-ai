import os
import json
import random
import asyncio
import logging
from PIL import Image
from google import genai
from google.genai import types
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.config import settings
from .state import ArticleState, AnalysisResponse, EditorContentResponse


# 스타일 래퍼 정의
WEBTOON_STYLE = "Modern digital webtoon art style, clean line art, vibrant cel-shading. Character must have consistent hair and outfit from the reference. "
CARDNEWS_STYLE = "Minimalist flat vector illustration, Instagram aesthetic, solid pastel background. Maintain exact same color palette and layout style. "

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", google_api_key=settings.GOOGLE_API_KEY)
client = genai.Client(api_key=settings.GOOGLE_API_KEY)

# 구조화된 출력용 LLM
analyze_llm = llm.with_structured_output(AnalysisResponse)
editor_llm = llm.with_structured_output(EditorContentResponse)



async def select_editor_node(state: ArticleState):
    """분류된 타입에 맞는 에디터를 JSON 데이터에서 선택"""
    # TODO: 에디터 선택 로직 개선
    editors = state["available_editors"]
    target_type = state["content_type"]
    
    candidates = [e for e in editors if e["type"] == target_type]
    selected = random.choice(candidates if candidates else editors)
    
    return {"editor": selected}


async def analyze_node(state: ArticleState):
    """뉴스 분석, 키워드 추출 및 타입 분류"""
    article = state['raw_article']
    
    prompt = f"""
    다음 뉴스를 분석해서 핵심 요약 3줄, 키워드(최대 5개),
    그리고 콘텐츠 타입(WEBTOON 또는 CARD_NEWS)을 결정해줘.
    내용 요약과 키워드는 반드시 한국어로 작성해야 해.

    제목: {article['title']}
    본문: {article['content']}
    """
    
    response = await analyze_llm.ainvoke(prompt)
    
    return {
        "summary": response.summary,
        "keywords": response.keywords,
        "content_type": response.content_type
    }


async def webtoon_creator_node(state: ArticleState):
    """웹툰 스타일 본문 및 이미지 프롬프트 생성"""
    editor = state['editor']
    article = state['raw_article']
    
    system_msg = SystemMessage(content=f"""
    {editor['persona_prompt']}
    너는 지금부터 이 뉴스를 4페이지 분량의 시각적 스토리보드로 재구성해야 해.
    
    [미션]
    1. 각 페이지의 'image_prompts'는 서로 다른 시각적 구도와 내용을 담아야 함.
    2. 1~4번이 하나의 흐름을 갖되, 시각적으로 중복되는 장면(동일한 각도나 반복되는 구도)은 절대 피할 것.
    3. 각 장면의 배경, 인물의 위치, 카메라의 거리를 AI가 서사에 맞춰 자유롭고 역동적으로 구성해줘.
    """)
    human_msg = HumanMessage(content=f"제목: {article['title']}\n내용: {article['content']}")
    
    response = await editor_llm.ainvoke([system_msg, human_msg])
    
    return {
        "final_title": response.final_title,
        "final_body": response.final_body,
        "image_prompts": response.image_prompts
    }


async def card_news_creator_node(state: ArticleState):
    """카드뉴스 스타일 본문 및 이미지 프롬프트 생성"""
    editor = state['editor']
    article = state['raw_article']
    
    system_msg = SystemMessage(content=f"""
    {editor['persona_prompt']}
    너는 복잡한 뉴스를 한눈에 들어오는 4장의 카드뉴스로 재구성해야 해.
    
    [미션]
    1. 4개의 'image_prompts'는 뉴스 본문의 핵심 정보를 단계별로 시각화해야 함.
    2. 각 페이지는 시각적 중복을 피하기 위해 레이아웃을 다르게 구성해:
       - 1번: 시선을 끄는 강력한 제목과 상징적인 아이콘
       - 2번: 핵심 수치나 데이터를 강조하는 차트 또는 다이어그램
       - 3번: 사건의 인과관계를 보여주는 단계별 레이아웃
       - 4번: 한눈에 들어오는 요약 리스트와 마무리 비주얼
    3. 모든 설명은 한국어로 작성하되, 'image_prompts' 내의 시각 묘사만 영어로 작성해줘.
    4. 디자인은 세련된 소셜 미디어 감성(Modern and trendy social media aesthetic)을 유지해.
    """)
    human_msg = HumanMessage(content=f"제목: {article['title']}\n내용: {article['content']}")
    
    response = await editor_llm.ainvoke([system_msg, human_msg])
    
    return {
        "final_title": response.final_title,
        "final_body": response.final_body,
        "image_prompts": response.image_prompts
    }


def save_local_image(content_key: str, idx: int, img: Image.Image) -> str:
    """이미지 로컬 저장 공통 유틸"""
    folder_path = os.path.join("output", content_key)
    os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, f"{idx}.png")
    img.save(file_path)
    return file_path


async def generate_image_task(content_key: str, idx: int, prompt: str, content_type: str, ref_image_path=None):
    """개별 이미지 생성 비동기 태스크"""
    style = WEBTOON_STYLE if content_type == "WEBTOON" else CARDNEWS_STYLE

    # 텍스트 지침 강화
    instruction = "Write all text for Korean readers. Use Korean for general text, but keep proper nouns, brand names, and English acronyms in English. Ensure all text is legible."
    if content_type == "CARD_NEWS":
        instruction += " Focus on infographic elements and consistent background color."
    
    final_prompt = f"{style} {prompt}. {instruction}"
    contents = [final_prompt]

    # 기준 이미지(이미지 0번)가 있으면 참조로 주입
    if ref_image_path and os.path.exists(ref_image_path):
        ref_img = Image.open(ref_image_path)
        contents.append(ref_img)
        contents[0] += " Use the reference image ONLY to maintain character/style consistency. IGNORE its composition and pose."

    try:
        response = await client.aio.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=['IMAGE'],
                image_config=types.ImageConfig(
                aspect_ratio="1:1",
                image_size="1K"
                )
            )
        )
        img = next((part.as_image() for part in response.parts if part.inline_data), None)
        if img:
            return save_local_image(content_key, idx, img)
    except Exception as e:
        logging.error(f"Error generating image {idx}: {e}")
    return None


async def image_gen_node(state: ArticleState):
    """[하이브리드 전략] 1번 생성 후 3번 병렬 생성"""
    content_key = state['raw_article']['content_key']
    content_type = state['content_type']
    prompts = state['image_prompts']
    
    # 1. 첫 번째 이미지(기준점) 생성
    anchor_image_path = await generate_image_task(content_key, 0, prompts[0], content_type)
    
    if not anchor_image_path:
        logging.error("기준 이미지 생성 실패")
        return {"error": "기준 이미지 생성 실패"}

    # 2. 남은 3장 병렬 생성
    tasks = [
        generate_image_task(content_key, i, prompts[i], content_type, anchor_image_path)
        for i in range(1, 4)
    ]
    
    parallel_paths = await asyncio.gather(*tasks)
    
    # 결과 합치기
    all_paths = [anchor_image_path] + [p for p in parallel_paths if p]
    return {"image_urls": all_paths}


async def final_save_node(state: ArticleState):
    """최종 결과물 저장"""
    article_data = state['raw_article']
    content_key = article_data['content_key']

    output_data = {
        "content_key": content_key,
        "source_article_ids": article_data['source_ids'],
        "content_type": state["content_type"],
        "editor": state["editor"]["name"],
        "title": state["final_title"],
        "body": state["final_body"],
        "summary": state["summary"],
        "keywords": state["keywords"],
        "image_prompts": state["image_prompts"],
        "images": state["image_urls"]
    }
    
    # TODO: S3 업로드 로직 추가
    file_path = f"output/{content_key}/content.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
        
    logging.info(f"최종 결과 저장: {file_path}")
    return state
