import asyncio
import logging
from sqlalchemy.sql import func
from sqlalchemy.orm import Session

from app.utils.image import download_image_from_url

from ..providers import ai_factory
from ..state import AiArticleState
from ..schemas import AnalysisResponse, EditorContentResponse
from ..prompts import (
    ARTICLE_ANALYSIS_TEMPLATE,
    create_webtoon_template,
    create_card_news_template,
)
from ..tasks.image import generate_openai_image_task, generate_google_image_task
from app.core.config import settings
from app.database.models import Editor, Category, AiArticle, ReactionCount, Issue, ProcessingStatusEnum
from app.utils.image import upload_image_to_s3

logger = logging.getLogger(__name__)

chat_model = ai_factory.get_chat_model()
analyze_llm = chat_model.with_structured_output(AnalysisResponse)
editor_llm = chat_model.with_structured_output(EditorContentResponse)


async def analyze_article(state: AiArticleState):
    """뉴스 분석"""
    context = state['raw_article_context']
    original_title = state['raw_article_title']

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


async def select_editor(state: AiArticleState):
    """DB에서 전문 분야(Category)가 일치하는 에디터 배정"""
    db: Session = state["db_session"]
    category_name = state["category_name"]

    matched_editor = (
        db.query(Editor)
        .join(Editor.categories)
        .filter(Category.name == category_name)
        .first()
    )

    if not matched_editor:
        matched_editor = db.query(Editor).order_by(func.random()).first()

    if not matched_editor:
        logger.error("Critical Error: No editors found in the database.")
        raise ValueError("에디터 데이터가 DB에 존재하지 않습니다.")

    logger.info(f"[SelectEditor] Assigned Editor: {matched_editor.name}, Category: {category_name}")

    return {
        "editor": {
            "id": matched_editor.id,
            "name": matched_editor.name,
            "persona_prompt": matched_editor.persona_prompt
        }
    }


async def draft_article(state: AiArticleState):
    """콘텐츠 타입(WEBTOON/CARD_NEWS)에 맞는 본문 및 이미지 프롬프트 생성"""
    editor = state['editor']
    content_type = state['content_type']

    template = (
        create_webtoon_template(editor['persona_prompt'])
        if content_type == "WEBTOON"
        else create_card_news_template(editor['persona_prompt'])
    )

    formatted_messages = template.format_messages(
        title=state['final_title'],
        content=state['raw_article_context']
    )

    response = await editor_llm.ainvoke(formatted_messages)

    return {
        "final_body": response.final_body,
        "image_prompts": response.image_prompts
    }


async def generate_images(state: AiArticleState):
    """이미지 병렬 생성"""
    content_key = state['content_key']
    content_type = state['content_type']
    prompts = state['image_prompts']

    images = []

    try:
        if settings.AI_PROVIDER == "google" and settings.GOOGLE_IMAGE_WITH_REFERENCE:
            logger.info(f"[GenerateImages] Using Gemini (reference) for {content_key}")

            agent_ref_image = None
            ref_url = state.get("reference_image_url")
            if ref_url:
                agent_ref_image = await download_image_from_url(ref_url)
                if agent_ref_image:
                    logger.info("[GenerateImages] Successfully downloaded agent reference image")
                else:
                    logger.warning("[GenerateImages] Failed to download agent reference image from URL")

            if agent_ref_image:
                logger.info(f"[GenerateImages] Generating anchor image based on Agent's content reference.")
                # 0번 이미지는 에이전트의 실사 이미지를 '내용(content)'으로 참조하여 생성
                anchor_image = await generate_google_image_task(0, prompts[0], content_type, ref_image=agent_ref_image, ref_type="content")
            else:
                logger.info(f"[GenerateImages] No agent reference image. Generating anchor image first.")
                anchor_image = await generate_google_image_task(0, prompts[0], content_type, ref_image=None)
            
            images.append(anchor_image)

            logger.info(f"[GenerateImages] Generating remaining images based on anchor image's style.")
            # 1~3번 이미지는 방금 만든 0번 이미지(만화풍)를 '스타일(style)'로 참조하여 생성
            tasks = [
                generate_google_image_task(i, prompts[i], content_type, ref_image=anchor_image, ref_type="style")
                for i in range(1, 4)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results, start=1):
                if isinstance(result, Exception):
                    raise ValueError(f"이미지 {i} 생성 실패: {result}") from result
                images.append(result)

        else:
            if settings.AI_PROVIDER == "openai":
                logger.info(f"[GenerateImages] Using OpenAI for {content_key}")
                task_func = generate_openai_image_task
            else:
                logger.info(f"[GenerateImages] Using Gemini (no reference) for {content_key}")
                task_func = generate_google_image_task

            tasks = [task_func(i, prompts[i], content_type) for i in range(4)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    raise ValueError(f"이미지 {i} 생성 실패: {result}") from result
                images.append(result)

        logger.info(f"[GenerateImages] All 4 images generated successfully. Uploading to S3...")
        image_urls = []
        for idx, img in enumerate(images):
            s3_url = await upload_image_to_s3(content_key, idx, img)
            if not s3_url:
                raise ValueError(f"S3 업로드 실패: 이미지 {idx}")
            image_urls.append(s3_url)

        logger.info(f"[GenerateImages] Successfully saved all images to S3 for {content_key}")
        return {"image_urls": image_urls}

    except Exception as e:
        logger.error(f"[GenerateImages] Generation failed for {content_key}: {e}")
        raise ValueError(f"이미지 생성 실패: {e}") from e


async def save_ai_article(state: AiArticleState):
    """최종 결과물 DB 저장"""
    db: Session = state['db_session']
    issue_id = state['issue_id']

    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    origin_articles_data = []
    if issue and issue.articles:
        origin_articles_data = [
            {"title": a.title, "url": a.origin_url}
            for a in issue.articles[:3]
        ]

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
    db.flush()

    new_reaction = ReactionCount(article_id=new_article.id)
    db.add(new_reaction)

    if issue:
        issue.processing_status = ProcessingStatusEnum.COMPLETED

    db.commit()

    logger.info(f"[SaveAiArticle] DB Saved: AiArticle ID {new_article.id}, Issue {issue_id} updated to processed.")
    return state
