import uuid
import logging
from sqlalchemy.orm import Session
from pathlib import Path
from app.engine.graph import create_graph
from app.core.database import SessionLocal
from app.database.models import Issue, Editor, Category

class WorkflowService:
    def __init__(self):
        self.graph = create_graph()

    async def run_ai_article_pipeline(self, issue_id: int):
        """
        여러 개의 연관 기사를 하나의 맥락으로 합쳐서 단일 AI 콘텐츠 생성
        """
        db: Session = SessionLocal()
        try:
            # 1. DB에서 이슈 및 관련 기사 조회
            issue = db.query(Issue).filter(Issue.id == issue_id).first()
            
            if not issue:
                logging.error(f"Issue ID {issue_id} not found.")
                return

            raw_articles = issue.articles
            if not raw_articles:
                logging.error(f"No articles found for Issue ID {issue_id}")
                return

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
                "raw_article_title": issue.issue_title,
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

            logging.info(f"[Workflow] Starting pipeline for Issue {issue_id}")
            
            # LangGraph 실행
            await self.graph.ainvoke(initial_state) 
            
            logging.info(f"[Workflow] Finished for Issue {issue_id}")

        except Exception as e:
            logging.error(f"[Workflow] Error: {e}", exc_info=True)
        finally:
            db.close()

workflow_service = WorkflowService()
