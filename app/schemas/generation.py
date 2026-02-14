from pydantic import BaseModel
from typing import List

class GenerationStatusResponse(BaseModel):
    status: str
    message: str

class AiArticleBatchGenerationRequest(BaseModel):
    issue_ids: List[int]

class TodayNewsnackRequest(BaseModel):
    issue_ids: List[int]
