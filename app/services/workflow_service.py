import json
import asyncio
from typing import List
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

    async def run_generation_pipeline(self, article_ids: List[int]):
        # TODO: 로컬 JSON 로드 로직을 DB 조회로 대체
        raw_articles = self._load_local_data("raw_articles.json")
        editors = self._load_local_data("editors.json")

        for target_id in article_ids:
            # 해당 ID의 기사 찾기
            article = next((a for a in raw_articles if a["id"] == target_id), None)
            if not article:
                continue

            # 초기 상태 구성
            initial_state = {
                "article_id": target_id,
                "raw_content": article["content"],
                "available_editors": editors,
                "content_type": None
            }

            try:
                # 랭그래프 실행
                await asyncio.to_thread(self.graph.invoke, initial_state)
            except Exception as e:
                print(f"Error processing {target_id}: {e}")

workflow_service = WorkflowService()
