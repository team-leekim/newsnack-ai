from typing import List, Literal
from pydantic import BaseModel, Field

class AnalysisResponse(BaseModel):
    """뉴스 분석 및 분류 결과"""
    title: str = Field(description="본문 내용을 바탕으로 최적화된 뉴스 제목")
    summary: List[str] = Field(description="핵심 요약 3줄 리스트 (~함, ~임 문체)")
    content_type: Literal["WEBTOON", "CARD_NEWS"] = Field(description="콘텐츠 타입 분류")

class EditorContentResponse(BaseModel):
    """에디터가 재작성한 본문 및 이미지 프롬프트"""
    final_body: str = Field(description="에디터 말투로 재작성된 전체 본문 내용")
    image_prompts: List[str] = Field(
        min_items=4,
        max_items=4,
        description=(
            "4 distinct visual descriptions in English that form a narrative flow of the news. "
            "Each prompt must describe a unique composition, subject, or perspective to ensure "
            "visual variety and avoid repetitive scenes."
        )
    )

class BriefingSegment(BaseModel):
    script: str = Field(description="해당 기사에 대한 30초 내외의 아나운서 낭독 대본")

class BriefingResponse(BaseModel):
    segments: List[BriefingSegment] = Field(description="입력된 기사들에 대한 순차적 대본 리스트")

class ImageValidationResponse(BaseModel):
    """이미지 적합성 검증 결과"""
    reason: str = Field(description="해당 이미지가 기사 문맥에 적합한지 판단한 이유 (판단의 근거)")
    is_valid: bool = Field(description="이미지가 조건을 충족하여 유효한지 여부 (유효하면 True, 거절 기준에 하나라도 해당되면 False)")
