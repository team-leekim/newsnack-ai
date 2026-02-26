import logging

from sqlalchemy.orm import Session

from ..providers import ai_factory
from ..state import TodayNewsnackState
from ..schemas import BriefingResponse
from ..prompts import create_briefing_template
from ..tasks.audio import generate_openai_audio_task, generate_google_audio_task
from app.core.config import settings
from app.database.models import AiArticle, TodayNewsnack
from app.utils.audio import get_audio_duration_from_bytes, calculate_article_timelines, upload_audio_to_s3

logger = logging.getLogger(__name__)

chat_model = ai_factory.get_chat_model()
briefing_llm = chat_model.with_structured_output(BriefingResponse)


async def fetch_articles(state: TodayNewsnackState):
    """지정된 이슈 ID에 해당하는 기사 조회 노드"""
    db: Session = state["db_session"]
    target_ids = state["target_issue_ids"]
    selected_articles = []

    if not target_ids:
        logger.warning("[FetchArticles] No target issue IDs provided.")
        return {"selected_articles": []}

    articles = (
        db.query(AiArticle)
        .filter(AiArticle.issue_id.in_(target_ids))
        .order_by(AiArticle.id.asc())
        .all()
    )

    article_map = {a.issue_id: a for a in articles}

    for issue_id in target_ids:
        if issue_id in article_map:
            a = article_map[issue_id]
            selected_articles.append({
                "id": a.id,
                "title": a.title,
                "body": a.body,
                "thumbnail_url": a.thumbnail_url
            })
        else:
            logger.warning(f"[FetchArticles] Targeted AiArticle for Issue {issue_id} not found.")

    logger.info(f"[FetchArticles] Fetched {len(selected_articles)} articles for briefing.")
    return {"selected_articles": selected_articles}


async def assemble_briefing(state: TodayNewsnackState):
    """구조화된 대본 생성 노드"""
    articles = state["selected_articles"]

    template = create_briefing_template(len(articles))
    formatted_messages = template.format_messages(articles=articles)

    response = await briefing_llm.ainvoke(formatted_messages)

    segments = []
    for original_article, generated_segment in zip(articles, response.segments):
        segments.append({
            "article_id": original_article["id"],
            "title": original_article["title"],
            "thumbnail_url": original_article["thumbnail_url"],
            "script": generated_segment.script
        })

    if len(articles) != len(response.segments):
        logger.warning(
            f"[AssembleBriefing] Count mismatch! Input: {len(articles)}, Output: {len(response.segments)}."
        )

    return {"briefing_segments": segments}


async def generate_audio(state: TodayNewsnackState):
    """단일 오디오 생성 및 타임라인 계산 노드"""
    segments = state["briefing_segments"]
    full_script = " ".join([s["script"] for s in segments])

    try:
        if settings.AI_PROVIDER == "openai":
            logger.info("[GenerateAudio] Using OpenAI TTS")
            audio_bytes = await generate_openai_audio_task(full_script)
        else:
            logger.info("[GenerateAudio] Using Google Gemini TTS")
            audio_bytes = await generate_google_audio_task(full_script)

        duration = get_audio_duration_from_bytes(audio_bytes)
        if not duration or duration <= 0:
            raise ValueError(f"Invalid audio duration: {duration}")

        briefing_articles_data = calculate_article_timelines(segments, duration)

        logger.info(f"[GenerateAudio] Successfully generated audio. Duration: {duration}s")
        return {
            "total_audio_bytes": audio_bytes,
            "briefing_articles_data": briefing_articles_data
        }

    except Exception as e:
        logger.error(f"[GenerateAudio] Failed to generate audio after retries: {e}")
        raise ValueError(f"오디오 생성 실패: {e}") from e


async def save_today_newsnack(state: TodayNewsnackState):
    """생성된 오디오 및 타임라인 저장 노드"""
    db: Session = state["db_session"]
    audio_bytes = state["total_audio_bytes"]
    articles_data = state["briefing_articles_data"]

    file_path = await upload_audio_to_s3(audio_bytes)
    if not file_path:
        logger.error("[SaveTodayNewsnack] Audio upload failed.")
        raise ValueError("오디오 업로드에 실패했습니다.")

    new_snack = TodayNewsnack(
        audio_url=file_path,
        briefing_articles=articles_data
    )

    db.add(new_snack)
    db.commit()

    logger.info(f"[SaveTodayNewsnack] Saved to DB. ID: {new_snack.id}, Path: {file_path}")
    return state
