from pydantic import BaseModel, Field
from typing import List

class AIContentCreateRequest(BaseModel):
    source_article_ids: List[int] = Field(..., description="생성 기점이 되는 원본 기사 ID 리스트")

class GenerationStatusResponse(BaseModel):
    status: str
    message: str
    processed_count: int
