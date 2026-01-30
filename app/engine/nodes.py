import os
import uuid
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
from datetime import datetime, timedelta

from .providers import ai_factory
from .state import ArticleState, AnalysisResponse, BriefingResponse, EditorContentResponse, TodayNewsnackState
from app.core.config import settings
from app.database.models import Editor, Category, AiArticle, ReactionCount, Issue, RawArticle, TodayNewsnack
from app.utils.audio import get_audio_duration_from_bytes, calculate_article_timelines

logger = logging.getLogger(__name__)

# 스타일 래퍼 정의
WEBTOON_STYLE = "Modern digital webtoon art style, clean line art, vibrant cel-shading. Character must have consistent hair and outfit from the reference. "
CARDNEWS_STYLE = "Minimalist flat vector illustration, Instagram aesthetic, solid pastel background. Maintain exact same color palette and layout style. "

# 현재 설정된 프로바이더의 LLM
llm = ai_factory.get_llm()

# 구조화된 출력용 LLM
analyze_llm = llm.with_structured_output(AnalysisResponse)
editor_llm = llm.with_structured_output(EditorContentResponse)
briefing_llm = llm.with_structured_output(BriefingResponse)


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
        logger.error("Critical Error: No editors found in the database.")
        raise ValueError("에디터 데이터가 DB에 존재하지 않습니다.")

    logger.info(f"Editor Assigned: {matched_editor.name} for Category {category_name}")

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
    """OpenAI를 사용한 개별 이미지 생성"""
    client = ai_factory.get_image_client()
    style = WEBTOON_STYLE if content_type == "WEBTOON" else CARDNEWS_STYLE
    final_prompt = f"{style} {prompt}. Ensure all text is in Korean if any."

    try:
        response = await client.images.generate(
            model=settings.OPENAI_IMAGE_MODEL,
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
        logger.error(f"Error generating OpenAI image {idx}: {e}")
        return None


async def generate_google_image_task(content_key: str, idx: int, prompt: str, content_type: str, ref_image_path=None):
    """Gemini를 사용한 개별 이미지 생성"""
    client = ai_factory.get_image_client()
    style = WEBTOON_STYLE if content_type == "WEBTOON" else CARDNEWS_STYLE

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
            model=settings.GOOGLE_IMAGE_MODEL,
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
        logger.error(f"Error generating image {idx}: {e}")
    return None


async def image_gen_node(state: ArticleState):
    """[하이브리드 전략] 1번 생성 후 3번 병렬 생성"""
    content_key = state['content_key']
    content_type = state['content_type']
    prompts = state['image_prompts']

    if settings.AI_PROVIDER == "openai":
        # OpenAI 전략: 참조 없이 4장 전면 병렬 생성
        logger.info(f"[ImageGen] Using OpenAI for {content_key}")
        tasks = [
            generate_openai_image_task(content_key, i, prompts[i], content_type)
            for i in range(4)
        ]
        image_paths = await asyncio.gather(*tasks)
        all_paths = [p for p in image_paths if p]
    else:
        # Google 전략: 1장 생성 후 3장 참조 병렬 생성
        logger.info(f"[ImageGen] Using Gemini for {content_key}")
        anchor_image_path = await generate_google_image_task(content_key, 0, prompts[0], content_type)
        if not anchor_image_path:
            return {"error": "기준 이미지 생성 실패"}

        tasks = [
            generate_google_image_task(content_key, i, prompts[i], content_type, anchor_image_path)
            for i in range(1, 4)
        ]
        parallel_paths = await asyncio.gather(*tasks)
        all_paths = [anchor_image_path] + [p for p in parallel_paths if p]

    return {"image_urls": all_paths}


async def final_save_node(state: ArticleState):
    """최종 결과물 DB 저장"""
    db: Session = state['db_session']
    issue_id = state['issue_id']
    
    # 1. 원본 기사 정보 추출 (최대 3개)
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    origin_articles_data = []
    if issue and issue.articles:
        origin_articles_data = [
            {"title": a.title, "url": a.origin_url}
            for a in issue.articles[:3]
        ]

    # 2. ai_article 테이블 저장 (통합형)
    new_article = AiArticle(
        issue_id=issue_id,
        content_type=state["content_type"],
        title=state["final_title"],
        thumbnail_url=state["image_urls"][0] if state["image_urls"] else None,
        editor_id=state["editor"]["id"],
        category_id=issue.category_id if issue else None,
        summary=state["summary"],
        body=state["final_body"],
        image_data={"image_urls": state["image_urls"]},
        origin_articles=origin_articles_data
    )
    db.add(new_article)
    db.flush() # ID를 얻기 위해 flush
    
    # 3. reaction_count 테이블 초기화
    new_reaction = ReactionCount(article_id=new_article.id)
    db.add(new_reaction)
    
    # 4. 상위 이슈 처리 상태 업데이트
    if issue:
        issue.is_processed = True
    
    db.commit()
    
    logger.info(f"DB Saved: AiArticle ID {new_article.id}, Issue {issue_id} updated to processed.")
    return state


async def select_hot_articles_node(state: TodayNewsnackState):
    """대상 기사 선정 노드"""
    db: Session = state["db_session"]
    selected_articles = []
    selected_issue_ids = set()

    # 최근 이슈 중에서 화제성 판단
    time_limit = datetime.now() - timedelta(hours=24)
    
    hot_issues = (
        db.query(Issue.id)
        .join(RawArticle, Issue.id == RawArticle.issue_id)
        .filter(Issue.is_processed == True)
        .filter(Issue.batch_time >= time_limit)
        .group_by(Issue.id)
        .order_by(func.count(RawArticle.id).desc())
        .limit(5)
        .all()
    )

    # 선정된 이슈의 AI 기사 가져오기
    for (issue_id,) in hot_issues:
        article = db.query(AiArticle).filter(AiArticle.issue_id == issue_id).first()
        if article:
            selected_articles.append(article)
            selected_issue_ids.add(issue_id)

    # 5개 미만이면, 최신 생성된 AI 기사로 채움
    if len(selected_articles) < 5:
        remaining = 5 - len(selected_articles)
        
        fallback_query = db.query(AiArticle).order_by(AiArticle.published_at.desc())
        
        if selected_issue_ids:
            fallback_query = fallback_query.filter(AiArticle.issue_id.notin_(selected_issue_ids))
            
        fallbacks = fallback_query.limit(remaining).all()
        selected_articles.extend(fallbacks)
    
    logger.info(f"[TodayNewsnack] Selected {len(selected_articles)} articles for briefing.")

    return {"selected_articles": [
        {
            "id": a.id,
            "title": a.title,
            "body": a.body,
            "thumbnail_url": a.thumbnail_url
        } for a in selected_articles
    ]}


async def assemble_briefing_node(state: TodayNewsnackState):
    """구조화된 대본 생성 노드"""
    articles = state["selected_articles"]
    
    # 아나운서 페르소나 주입 프롬프트
    prompt = f"""
    당신은 '뉴스낵(newsnack)'의 메인 마스코트인 '박수박사수달'입니다. 
    아래 제공된 {len(articles)}개의 뉴스 기사 순서대로 브리핑 대본을 작성하세요.

    [아나운서 페르소나 가이드]
    1. 말투: 20대 후반의 활기차고 지적인 친구 같은 느낌. (~해요, ~네요 문체 사용)
    2. 성격: 뉴스를 전하는 게 너무 즐거운 에너지 넘치는 수달.
    3. 특징: 
    - 오프닝: "안녕하세요! 오늘의 뉴스낵을 시작할게요."처럼 밝게 시작.
    - 클로징: "오늘 소식은 여기까지예요. 오늘도 즐거운 하루 보내세요!" 등 인사.
    - 각 기사 대본 사이에 자연스러운 연결 멘트(브릿지)를 포함할 것.

    [제약 사항]
    1. 반드시 입력된 기사 순서와 동일하게 {len(articles)}개의 대본 세그먼트를 생성할 것.
    2. 각 기사당 150-200자 내외(30초)의 분량으로 작성할 것.
    3. 각 기사의 핵심 정보는 반드시 포함하되, 에디터의 개별 말투는 지우고 '박수박사수달'의 톤으로 재창조할 것.
    4. 전문 용어는 최대한 쉽게 풀어서 설명할 것.

    [뉴스 데이터]
    {articles}
    """
    
    response = await briefing_llm.ainvoke(prompt)
    
    # 기사 정보와 대본 매핑
    segments = []
    for original_article, generated_segment in zip(articles, response.segments):
        segments.append({
            "article_id": original_article["id"],
            "title": original_article["title"],
            "thumbnail_url": original_article["thumbnail_url"],
            "script": generated_segment.script
        })
    
    # 개수가 불일치한 경우
    if len(articles) != len(response.segments):
        logger.warning(
            f"[AssembleBriefing] Count mismatch! Input: {len(articles)}, Output: {len(response.segments)}."
        )
    
    return {"briefing_segments": segments}


async def generate_openai_audio_task(full_script: str):
    """OpenAI 전용 오디오 생성 태스크"""
    client = ai_factory.get_audio_client()
    
    async with client.audio.speech.with_streaming_response.create(
        model=settings.OPENAI_TTS_MODEL,
        voice=settings.OPENAI_TTS_VOICE,
        input=full_script,
        instructions=settings.OPENAI_TTS_INSTRUCTIONS
    ) as response:
        # 전체 오디오 바이너리를 메모리로 읽어옴
        audio_bytes = await response.read()
    
    return audio_bytes


async def generate_audio_node(state: TodayNewsnackState):
    """단일 오디오 생성 및 타임라인 계산 노드"""
    segments = state["briefing_segments"]
    # 5개 기사 대본을 하나로 합침
    full_script = " ".join([s["script"] for s in segments])
    
    if settings.AI_PROVIDER == "openai":
        audio_bytes = await generate_openai_audio_task(full_script)
    else:
        # TODO: 추후 Google TTS 태스크 구현
        raise NotImplementedError("Google TTS is not implemented yet.")
    
    # 오디오 길이 측정 및 타임라인 계산
    duration = get_audio_duration_from_bytes(audio_bytes)
    briefing_articles_data = calculate_article_timelines(segments, duration)
    
    return {
        "total_audio_bytes": audio_bytes,
        "briefing_articles_data": briefing_articles_data
    }


def save_local_audio(audio_bytes: bytes) -> str:
    """오디오 로컬 저장 공통 유틸"""
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    file_name = f"{uuid.uuid4().hex}.mp3" 
    file_path = os.path.join(output_dir, file_name)

    with open(file_path, "wb") as f:
        f.write(audio_bytes)
    return file_path


async def save_today_newsnack_node(state: TodayNewsnackState):
    """생성된 오디오 및 타임라인 저장 노드"""
    db: Session = state["db_session"]
    audio_bytes = state["total_audio_bytes"]
    articles_data = state["briefing_articles_data"]
    
    # 생성된 오디오 저장
    # TODO: S3 업로드 로직으로 변경
    file_path = save_local_audio(audio_bytes)
    
    # DB 저장
    new_snack = TodayNewsnack(
        audio_url=file_path,
        briefing_articles=articles_data,
        published_at=datetime.now()
    )
    
    db.add(new_snack)
    db.commit()
    
    logger.info(f"[TodayNewsnack] Saved to DB. ID: {new_snack.id}, Path: {file_path}")
    return state
