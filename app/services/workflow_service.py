import asyncio
import uuid
import logging
from typing import List
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.engine.graph import create_ai_article_graph, create_today_newsnack_graph
from app.core.config import settings
from app.core.database import SessionLocal
from app.database.models import Issue, Editor, Category, ProcessingStatusEnum


logger = logging.getLogger(__name__)

class WorkflowService:
    def __init__(self):
        self.graph = create_ai_article_graph()
        self.newsnack_graph = create_today_newsnack_graph()
        self.semaphore = asyncio.Semaphore(settings.AI_ARTICLE_MAX_CONCURRENT_GENERATIONS)

    async def run_batch_ai_articles_pipeline(self, issue_ids: List[int]):
        """
        여러 이슈를 배치로 처리하되, 세마포어로 동시 실행 수를 제한함
        """
        async def wrapped_pipeline(issue_id: int):
            # 세마포어 획득
            async with self.semaphore:
                await asyncio.sleep(settings.AI_ARTICLE_GENERATION_DELAY_SECONDS)

                logger.info(f"[Batch] Starting issue {issue_id}")
                await self.run_ai_article_pipeline(issue_id)
        
        # 모든 이슈에 대해 작업 생성 후 동시에 실행
        tasks = [wrapped_pipeline(iid) for iid in issue_ids]
        await asyncio.gather(*tasks)

    async def run_ai_article_pipeline(self, issue_id: int):
        """
        AI 기사 생성 파이프라인 실행
        """
        db: Session = SessionLocal()
        try:
            # 1. DB에서 이슈 및 관련 기사 조회
            issue = db.query(Issue).filter(Issue.id == issue_id).first()
            if not issue:
                logger.error(f"Issue ID {issue_id} not found.")
                return

            # 중복 요청 방지: PENDING만 허용
            if issue.processing_status != ProcessingStatusEnum.PENDING:
                logger.warning(f"Issue {issue_id} is not PENDING (current: {issue.processing_status}), rejecting request.")
                raise HTTPException(status_code=409, detail="Issue is already being processed or completed.")

            raw_articles = issue.articles
            if not raw_articles:
                logger.error(f"No articles found for Issue ID {issue_id}")
                return

            # 상태 IN_PROGRESS로 변경
            issue.processing_status = ProcessingStatusEnum.IN_PROGRESS
            db.commit()

            # 2. 본문 통합 (프롬프트 입력용)
            merged_content = "\n\n---\n\n".join([
                f"기사 제목: {a.title}\n본문: {a.content}"
                for a in raw_articles
            ])

            generated_content_key = str(uuid.uuid4())

            # 3. LangGraph 초기 상태 구성
            initial_state = {
                "db_session": db,
                "issue_id": issue.id,
                "category_name": issue.category.name if issue.category else "General",
                "raw_article_context": merged_content,
                "raw_article_title": issue.title,
                "content_key": generated_content_key,
                # 결과값 초기화
                "editor": None,
                "summary": [],
                "content_type": "",
                "final_title": "",
                "final_body": "",
                "image_prompts": [],
                "image_urls": []
            }

            logger.info(f"[Workflow] Starting pipeline for Issue {issue_id}")

            # LangGraph 실행
            await self.graph.ainvoke(initial_state)

            logger.info(f"[Workflow] Finished for Issue {issue_id}")

        except Exception as e:
            # 실패 시 FAILED로 변경
            issue = db.query(Issue).filter(Issue.id == issue_id).first()
            if issue:
                issue.processing_status = ProcessingStatusEnum.FAILED
                db.commit()
            logger.error(f"[Workflow] Error: {e}", exc_info=True)
            raise
        finally:
            db.close()

    async def run_today_newsnack_pipeline(self):
        """오늘의 뉴스낵 생성 파이프라인 실행"""
        db = SessionLocal()
        try:
            initial_state = {
                "db_session": db,
                "selected_articles": [],
                "briefing_segments": [],
                "total_audio_bytes": b"",
                "audio_url": "",
                "briefing_articles_data": []
            }
            
            logger.info("[Workflow] Starting Today's Newsnack Pipeline")
            await self.newsnack_graph.ainvoke(initial_state)
            logger.info("[Workflow] Today's Newsnack Pipeline Completed")
            
        except Exception as e:
            logger.error(f"[Workflow] Error in Newsnack Pipeline: {e}", exc_info=True)
        finally:
            db.close()

workflow_service = WorkflowService()
