import uuid
import json
import logging
from pathlib import Path
from app.engine.graph import create_graph

class WorkflowService:
    def __init__(self):
        self.graph = create_graph()
        # 로컬 경로 설정
        self.base_path = Path(__file__).parent.parent.parent / "data"

    def _load_local_data(self, filename: str):
        with open(self.base_path / filename, "r", encoding="utf-8") as f:
            return json.load(f)

    async def run_ai_article_pipeline(self, issue_id: int):
        """
        여러 개의 연관 기사를 하나의 맥락으로 합쳐서 단일 AI 콘텐츠 생성
        """
        # TODO: DB 조회 방식으로 변경
        source_article_ids = [1]
        all_raw_articles = self._load_local_data("raw_articles.json")
        editors = self._load_local_data("editors.json")

        # 1. 요청받은 ID들에 해당하는 기사 추출
        target_articles = [a for a in all_raw_articles if a["id"] in source_article_ids]
        if not target_articles: return

        # 2. 본문 통합
        merged_content = "\n\n---\n\n".join([
            f"기사 제목: {a['title']}\n본문: {a['content']}" 
            for a in target_articles
        ])

        integrated_article = {
            "content_key": str(uuid.uuid4()),
            "source_ids": source_article_ids,
            "title": target_articles[0]["title"],
            "content": merged_content,
            "category": target_articles[0]["category"]
        }

        # 3. 랭그래프 초기 상태 구성
        initial_state = {
            "raw_article": integrated_article,
            "editor": None,
            "available_editors": editors,
            "summary": [],
            "keywords": [],
            "content_type": "",
            "final_title": "",
            "final_body": "",
            "image_prompts": [],
            "image_urls": [],
            "error": None
        }

        try:
            logging.info(f"[Workflow] Starting single pipeline for issue with {len(target_articles)} articles")
            # 랭그래프 실행
            await self.graph.ainvoke(initial_state) 
            logging.info(f"[Workflow] Successfully generated AI content for IDs: {source_article_ids}")
        except Exception as e:
            logging.error(f"[Workflow] Error during generation for {source_article_ids}: {e}", exc_info=True)

workflow_service = WorkflowService()
