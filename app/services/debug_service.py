import logging
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.database.models import Issue
from app.engine.nodes.ai_article import analyze_article
from app.engine.nodes.image_researcher import image_researcher
from app.engine.nodes.image_validation import validate_image

logger = logging.getLogger(__name__)

class DebugService:
    async def _prepare_and_research_state(self, issue_id: int, db: Session) -> dict:
        """공통 로직: 이슈 조회, 분석, 이미지 리서치를 수행하고 state를 반환합니다."""
        issue = db.query(Issue).filter(Issue.id == issue_id).first()
        if not issue:
            raise ValueError(f"Issue ID {issue_id} not found.")

        raw_articles = issue.articles
        if not raw_articles:
            raise ValueError(f"No articles found for Issue ID {issue_id}")

        merged_content = "\n\n---\n\n".join([
            f"기사 제목: {a.title}\n본문: {a.content}"
            for a in raw_articles
        ])

        state = {
            "raw_article_context": merged_content,
            "raw_article_title": issue.title,
        }
        state = await analyze_article(state)

        research_result = await image_researcher(state)
        state.update(research_result)
        return state

    async def run_image_research_debug(self, issue_id: int) -> dict:
        """
        [DEBUG] analyze_article + image_research 두 단계만 실행하여 참조 이미지 URL만 반환.
        DB 상태를 변경하지 않음.
        """
        db = SessionLocal()
        try:
            state = await self._prepare_and_research_state(issue_id, db)
            return {
                "issue_id": issue_id,
                "final_title": state.get("final_title", ""),
                "summary": state.get("summary", []),
                "reference_image_url": state.get("reference_image_url"),
            }
        finally:
            db.close()

    async def run_image_research_and_validate_debug(self, issue_id: int):
        """
        [DEBUG] analyze_article + image_research + image_validator 세 단계만 실행하여 참조 이미지 URL만 반환.
        DB 상태를 변경하지 않음.
        """
        db = SessionLocal()
        try:
            state = await self._prepare_and_research_state(issue_id, db)

            # 이미지 검증 실행
            validation_result = await validate_image(state)
            state.update(validation_result)

            # ImageValidationResponse가 포함된 상태를 반영하여 리턴합니다.
            return {
                "issue_id": issue_id,
                "final_title": state.get("final_title", ""),
                "summary": state.get("summary", []),
                "reference_image_url": state.get("reference_image_url")
            }
        finally:
            db.close()

debug_service = DebugService()
