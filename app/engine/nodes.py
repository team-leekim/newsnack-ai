import os
import asyncio
import logging
import base64
from io import BytesIO
from PIL import Image
from google.genai import types
from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from langchain_core.messages import SystemMessage, HumanMessage
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_random_exponential

from .providers import ai_factory
from .state import AiArticleState, AnalysisResponse, BriefingResponse, EditorContentResponse, TodayNewsnackState
from .prompts import (
    ARTICLE_ANALYSIS_TEMPLATE,
    create_webtoon_template,
    create_card_news_template,
    create_briefing_template,
    ImageStyle,
    create_image_prompt,
    create_google_image_prompt,
)
from app.core.config import settings
from app.database.models import Editor, Category, AiArticle, ReactionCount, Issue, RawArticle, TodayNewsnack
from app.utils.image import upload_image_to_s3
from app.utils.audio import convert_pcm_to_mp3, get_audio_duration_from_bytes, calculate_article_timelines, upload_audio_to_s3
from app.engine.prompts import TTS_INSTRUCTIONS, create_tts_prompt

logger = logging.getLogger(__name__)

# 현재 설정된 프로바이더의 LLM
llm = ai_factory.get_llm()

# 구조화된 출력용 LLM
analyze_llm = llm.with_structured_output(AnalysisResponse)
editor_llm = llm.with_structured_output(EditorContentResponse)
briefing_llm = llm.with_structured_output(BriefingResponse)


async def select_editor_node(state: AiArticleState):
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


async def analyze_article_node(state: AiArticleState):
    """뉴스 분석"""
    context = state['raw_article_context']
    original_title = state['raw_article_title']
    
    # 프롬프트 템플릿에서 메시지 생성
    formatted_messages = ARTICLE_ANALYSIS_TEMPLATE.format_messages(
        original_title=original_title,
        content=context
    )
    
    response = await analyze_llm.ainvoke(formatted_messages)

    return {
        "final_title": response.title,
        "summary": response.summary,
        "content_type": response.content_type
    }


async def webtoon_creator_node(state: AiArticleState):
    """웹툰 스타일 본문 및 이미지 프롬프트 생성"""
    editor = state['editor']
    title = state['final_title']
    context = state['raw_article_context']
    
    # 에디터의 페르소나를 포함한 템플릿 생성 및 메시지 포맷
    template = create_webtoon_template(editor['persona_prompt'])
    formatted_messages = template.format_messages(
        title=title,
        content=context
    )
    
    response = await editor_llm.ainvoke(formatted_messages)
    
    return {
        "final_body": response.final_body,
        "image_prompts": response.image_prompts
    }


async def card_news_creator_node(state: AiArticleState):
    """카드뉴스 스타일 본문 및 이미지 프롬프트 생성"""
    editor = state['editor']
    title = state['final_title']
    context = state['raw_article_context']
    
    # 에디터의 페르소나를 포함한 템플릿 생성 및 메시지 포맷
    template = create_card_news_template(editor['persona_prompt'])
    formatted_messages = template.format_messages(
        title=title,
        content=context
    )
    
    response = await editor_llm.ainvoke(formatted_messages)
    
    return {
        "final_body": response.final_body,
        "image_prompts": response.image_prompts
    }


@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, min=2, max=10)
)
async def generate_openai_image_task(idx: int, prompt: str, content_type: str) -> Image.Image:
    """OpenAI를 사용한 개별 이미지 생성 (재시도 포함)"""
    client = ai_factory.get_image_client()
    style = ImageStyle.get_style(content_type)
    final_prompt = create_image_prompt(style, prompt)

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
        
        return img  # PIL Image 객체 반환
        
    except Exception as e:
        logger.error(f"Error generating OpenAI image {idx}: {e}")
        raise


@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, min=2, max=10)
)
async def generate_google_image_task(idx: int, prompt: str, content_type: str, ref_image: Image.Image = None) -> Image.Image:
    """Gemini를 사용한 개별 이미지 생성 (재시도 포함, 메모리 기반 참조)"""
    client = ai_factory.get_image_client()
    style = ImageStyle.get_style(content_type)
    
    # 프롬프트 생성 (참조 이미지 사용 여부 반영)
    with_reference = bool(ref_image is not None)
    final_prompt = create_google_image_prompt(
        style=style,
        prompt=prompt,
        content_type=content_type,
        with_reference=with_reference
    )
    contents = [final_prompt]

    # 참조 이미지가 있으면 메모리의 PIL Image 객체를 주입
    if with_reference:
        contents.append(ref_image)

    image_model = (
        settings.GOOGLE_IMAGE_MODEL_WITH_REFERENCE
        if settings.GOOGLE_IMAGE_WITH_REFERENCE
        else settings.GOOGLE_IMAGE_MODEL
    )

    config_params = {"aspect_ratio": "1:1"}
    if settings.GOOGLE_IMAGE_WITH_REFERENCE:
        config_params["image_size"] = "1K"
    image_config = types.ImageConfig(**config_params)

    try:
        response = await client.aio.models.generate_content(
            model=image_model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=['IMAGE'],
                image_config=image_config
            )
        )
        img_part = next((part.inline_data for part in response.parts if part.inline_data), None)
        if img_part:
            img = Image.open(BytesIO(img_part.data))
            return img  # PIL Image 객체 반환
        else:
            raise ValueError(f"No image data in response for image {idx}")
    except Exception as e:
        logger.error(f"Error generating image {idx}: {e}")
        raise


async def image_gen_node(state: AiArticleState):
    """이미지 병렬 생성"""
    content_key = state['content_key']
    content_type = state['content_type']
    prompts = state['image_prompts']
    
    images = []  # PIL Image 객체들을 메모리에 보관
    
    try:
        if settings.AI_PROVIDER == "openai":
            logger.info(f"[ImageGen] Using OpenAI for {content_key}")
            tasks = [
                generate_openai_image_task(i, prompts[i], content_type)
                for i in range(4)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    raise ValueError(f"이미지 {i} 생성 실패: {result}") from result
                images.append(result)
            
        else:
            if settings.GOOGLE_IMAGE_WITH_REFERENCE:
                logger.info(f"[ImageGen] Using Gemini (reference) for {content_key}")
                
                # 0번 이미지 생성 (기준 이미지)
                anchor_image = await generate_google_image_task(0, prompts[0], content_type, ref_image=None)
                images.append(anchor_image)
                
                # 1-3번 이미지 생성 (0번 이미지를 참조로 사용)
                tasks = [
                    generate_google_image_task(i, prompts[i], content_type, ref_image=anchor_image)
                    for i in range(1, 4)
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for i, result in enumerate(results, start=1):
                    if isinstance(result, Exception):
                        raise ValueError(f"이미지 {i} 생성 실패: {result}") from result
                    images.append(result)
                
            else:
                logger.info(f"[ImageGen] Using Gemini (no reference) for {content_key}")
                tasks = [
                    generate_google_image_task(i, prompts[i], content_type)
                    for i in range(4)
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        raise ValueError(f"이미지 {i} 생성 실패: {result}") from result
                    images.append(result)
        
        # 모든 이미지가 성공적으로 생성되었을 때만 S3 업로드
        logger.info(f"[ImageGen] All 4 images generated successfully. Uploading to S3...")
        image_urls = []
        for idx, img in enumerate(images):
            s3_url = await upload_image_to_s3(content_key, idx, img)
            if not s3_url:
                raise ValueError(f"S3 업로드 실패: 이미지 {idx}")
            image_urls.append(s3_url)
        
        logger.info(f"[ImageGen] Successfully saved all images to S3 for {content_key}")
        return {"image_urls": image_urls}
        
    except Exception as e:
        logger.error(f"[ImageGen] Generation failed for {content_key}: {e}")
        raise ValueError(f"이미지 생성 실패: {e}") from e


async def save_ai_article_node(state: AiArticleState):
    """최종 결과물 DB 저장"""
    # TODO: 이미지 생성에 실패한 경우 예외 처리 필요
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

    # 2. ai_article 테이블 저장
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
    time_limit = datetime.now() - timedelta(hours=settings.TODAY_NEWSNACK_ISSUE_TIME_WINDOW_HOURS)
    
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
    
    # 기사 개수를 반영한 브리핑 템플릿 생성 및 메시지 포맷
    template = create_briefing_template(len(articles))
    formatted_messages = template.format_messages(articles=articles)
    
    response = await briefing_llm.ainvoke(formatted_messages)
    
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


@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, min=2, max=10)
)
async def generate_google_audio_task(full_script: str):
    """Google Gemini TTS를 사용한 오디오 생성 태스크 (재시도 포함)"""
    
    client = ai_factory.get_audio_client()
    prompt = create_tts_prompt(full_script)
    
    try:
        response = await client.aio.models.generate_content(
            model=settings.GOOGLE_TTS_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=settings.GOOGLE_TTS_VOICE
                        )
                    )
                )
            )
        )

        raw_pcm = response.candidates[0].content.parts[0].inline_data.data
        audio_bytes = convert_pcm_to_mp3(raw_pcm)
        
        if not audio_bytes:
            raise ValueError("Failed to convert PCM to MP3")
        
        return audio_bytes
    except Exception as e:
        logger.error(f"Error generating Google audio: {e}")
        raise


@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, min=2, max=10)
)
async def generate_openai_audio_task(full_script: str):
    """OpenAI 전용 오디오 생성 태스크 (재시도 포함)"""
    
    client = ai_factory.get_audio_client()
    
    try:
        async with client.audio.speech.with_streaming_response.create(
            model=settings.OPENAI_TTS_MODEL,
            voice=settings.OPENAI_TTS_VOICE,
            input=full_script,
            instructions=TTS_INSTRUCTIONS
        ) as response:
            # 전체 오디오 바이너리를 메모리로 읽어옴
            audio_bytes = await response.read()
        
        if not audio_bytes:
            raise ValueError("Failed to read audio from OpenAI response")
        
        return audio_bytes
    except Exception as e:
        logger.error(f"Error generating OpenAI audio: {e}")
        raise


async def generate_audio_node(state: TodayNewsnackState):
    """단일 오디오 생성 및 타임라인 계산 노드"""
    segments = state["briefing_segments"]
    # 5개 기사 대본을 하나로 합침
    full_script = " ".join([s["script"] for s in segments])
    
    try:
        if settings.AI_PROVIDER == "openai":
            logger.info("[AudioGen] Using OpenAI TTS")
            audio_bytes = await generate_openai_audio_task(full_script)
        else:
            logger.info("[AudioGen] Using Google Gemini TTS")
            audio_bytes = await generate_google_audio_task(full_script)
        
        # 오디오 길이 측정 및 타임라인 계산
        duration = get_audio_duration_from_bytes(audio_bytes)
        if not duration or duration <= 0:
            raise ValueError(f"Invalid audio duration: {duration}")
        
        briefing_articles_data = calculate_article_timelines(segments, duration)
        
        logger.info(f"[AudioGen] Successfully generated audio. Duration: {duration}s")
        return {
            "total_audio_bytes": audio_bytes,
            "briefing_articles_data": briefing_articles_data
        }
    
    except Exception as e:
        logger.error(f"[AudioGen] Failed to generate audio after retries: {e}")
        raise ValueError(f"오디오 생성 실패: {e}") from e


async def save_today_newsnack_node(state: TodayNewsnackState):
    """생성된 오디오 및 타임라인 저장 노드"""
    # TODO: 오디오 생성에 실패한 경우 예외 처리 필요
    db: Session = state["db_session"]
    audio_bytes = state["total_audio_bytes"]
    articles_data = state["briefing_articles_data"]
    
    # 생성된 오디오 저장
    file_path = await upload_audio_to_s3(audio_bytes)
    if not file_path:
        logger.error("[TodayNewsnack] Audio upload failed.")
        raise ValueError("오디오 업로드에 실패했습니다.")
    
    # DB 저장
    new_snack = TodayNewsnack(
        audio_url=file_path,
        briefing_articles=articles_data
    )
    
    db.add(new_snack)
    db.commit()
    
    logger.info(f"[TodayNewsnack] Saved to DB. ID: {new_snack.id}, Path: {file_path}")
    return state
