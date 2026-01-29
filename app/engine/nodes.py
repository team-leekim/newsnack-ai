import os
import asyncio
import logging
import base64
from io import BytesIO
from PIL import Image
from google import genai
from google.genai import types
from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from langchain_core.messages import SystemMessage, HumanMessage

from .providers import ai_factory
from .state import ArticleState, AnalysisResponse, EditorContentResponse
from app.core.config import settings
from app.database.models import Editor, AiContent, AiArticle, Category, EditorCategory

# 스타일 래퍼 정의
WEBTOON_STYLE = "Modern digital webtoon art style, clean line art, vibrant cel-shading. Character must have consistent hair and outfit from the reference. "
CARDNEWS_STYLE = "Minimalist flat vector illustration, Instagram aesthetic, solid pastel background. Maintain exact same color palette and layout style. "

# 현재 설정된 프로바이더의 LLM
llm = ai_factory.get_llm()
client = genai.Client(api_key=settings.GOOGLE_API_KEY)

# 구조화된 출력용 LLM
analyze_llm = llm.with_structured_output(AnalysisResponse)
editor_llm = llm.with_structured_output(EditorContentResponse)


async def select_editor_node(state: ArticleState):
    """DB에서 전문 분야(Category)가 일치하는 에디터 배정"""
    db: Session = state["db_session"]
    category_name = state["category_name"]
    
    # 1. 카테고리 매칭 에디터 조회
    matched_editor = (
        db.query(Editor)
        .join(Editor.categories)
        .filter(Category.name == category_name)
        .first()
    )
    
    # 2. 없으면 랜덤으로 배정
    if not matched_editor:
        matched_editor = db.query(Editor).order_by(func.random()).first()

    # DB에 에디터가 단 하나도 없는 경우 처리
    if not matched_editor:
        logging.error("Critical Error: No editors found in the database.")
        raise ValueError("에디터 데이터가 DB에 존재하지 않습니다.")

    logging.info(f"Editor Assigned: {matched_editor.name} for Category {category_name}")

    # 3. 객체를 Dict로 변환
    return {
        "editor": {
            "id": matched_editor.id,
            "name": matched_editor.name,
            "persona_prompt": matched_editor.persona_prompt
        }
    }


async def analyze_node(state: ArticleState):
    """뉴스 분석"""
    context = state['raw_article_context']
    original_title = state['raw_article_title']
    
    prompt = f"""
    당신은 뉴스 큐레이션 전문가입니다. 다음 뉴스를 분석하여 제목을 최적화하고 내용을 요약하세요.

    [작업 가이드라인]
    1. 제목(title): 
       - 원본 제목과 본문 내용을 바탕으로 기사의 **핵심 내용을 가장 잘 나타내는 짧고 간결한 제목**을 생성할 것.
       - **최대 15자 내외**로 작성하여 한눈에 들어오도록 할 것.
       - 독자의 흥미를 유발하되, **과장 없이 명확한 키워드**를 포함할 것.
       - 문체를 변경하거나 감정을 섞지 말고, **객관적인 언론사 기사 제목**처럼 작성할 것.
    2. 요약(summary):
       - 반드시 3줄로 작성할 것.
       - 핵심 위주로 아주 짧고 간결하게 작성할 것.
       - 문장 끝을 '~함', '~임', '~함'과 같은 명사형 어미로 끝낼 것. (예: 삼성전자 실적 발표함, 금리 인상 결정됨)
    3. 분류(content_type):
       - 서사성/감정 중심이면 'WEBTOON', 정보/데이터 중심이면 'CARD_NEWS'로 분류할 것.

    [분석 대상]
    원본 제목: {original_title}
    본문 내용: {context}

    [출력 요구사항]
    - title: 최적화된 제목
    - summary: 명사형 어미를 사용한 3줄 요약
    - content_type: 분류 결과
    """
    
    response = await analyze_llm.ainvoke(prompt)

    return {
        "final_title": response.title,
        "summary": response.summary,
        "content_type": response.content_type
    }


async def webtoon_creator_node(state: ArticleState):
    """웹툰 스타일 본문 및 이미지 프롬프트 생성"""
    editor = state['editor']
    title = state['final_title']
    context = state['raw_article_context']
    
    system_msg = SystemMessage(content=f"""
    {editor['persona_prompt']}
    너는 지금부터 이 뉴스를 4페이지 분량의 시각적 스토리보드로 재구성해야 해.
    
    [미션]
    1. 각 페이지의 'image_prompts'는 서로 다른 시각적 구도와 내용을 담아야 함.
    2. 1~4번이 하나의 흐름을 갖되, 시각적으로 중복되는 장면(동일한 각도나 반복되는 구도)은 절대 피할 것.
    3. 각 장면의 배경, 인물의 위치, 카메라의 거리를 AI가 서사에 맞춰 자유롭고 역동적으로 구성해줘.
    """)
    human_msg = HumanMessage(content=f"제목: {title}\n내용: {context}")
    
    response = await editor_llm.ainvoke([system_msg, human_msg])
    
    return {
        "final_body": response.final_body,
        "image_prompts": response.image_prompts
    }


async def card_news_creator_node(state: ArticleState):
    """카드뉴스 스타일 본문 및 이미지 프롬프트 생성"""
    editor = state['editor']
    title = state['final_title']
    context = state['raw_article_context']
    
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
    human_msg = HumanMessage(content=f"제목: {title}\n내용: {context}")
    
    response = await editor_llm.ainvoke([system_msg, human_msg])
    
    return {
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


async def generate_openai_image_task(content_key: str, idx: int, prompt: str, content_type: str):
    """OpenAI를 사용한 독립적 이미지 생성"""
    client = ai_factory.get_image_client()
    style = WEBTOON_STYLE if content_type == "WEBTOON" else CARDNEWS_STYLE
    final_prompt = f"{style} {prompt}. Ensure all text is in Korean if any."

    try:
        response = await client.images.generate(
            model="gpt-image-1.5",
            prompt=final_prompt,
            n=1,
            quality="low", #TODO: 추후 결과물 품질에 따라 조정
            size="1024x1024"
        )
        
        # Base64 데이터 추출 및 PIL 이미지 변환
        b64_data = response.data[0].b64_json
        img_data = base64.b64decode(b64_data)
        img = Image.open(BytesIO(img_data))
        
        return save_local_image(content_key, idx, img)
        
    except Exception as e:
        logging.error(f"Error generating OpenAI image {idx}: {e}")
        return None


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
    content_key = state['content_key']
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
    """최종 결과물 DB 저장"""
    db: Session = state['db_session']
    
    # 1. 상위 콘텐츠 테이블 저장
    new_content = AiContent(
        content_type=state["content_type"],
        thumbnail_url=state["image_urls"][0] if state["image_urls"] else None
    )
    db.add(new_content)
    db.flush()
    
    # 2. 상세 기사 테이블 저장
    cat = db.query(Category).filter(Category.name == state["category_name"]).first()
    
    new_article = AiArticle(
        ai_content_id=new_content.id,
        title=state["final_title"],
        editor_id=state["editor"]["id"],
        category_id=cat.id if cat else None,
        summary=state["summary"],
        body=state["final_body"],
        image_data={"image_urls": state["image_urls"]}
    )
    db.add(new_article)
    db.commit()
    
    logging.info(f"DB Saved: AiContent ID {new_content.id}")
    return state
